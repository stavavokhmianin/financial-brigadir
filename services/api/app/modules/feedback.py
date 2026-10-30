"""Обратная связь по тратам (ADR-0007, п. 4): что спросить и как метка меняет прогноз.

Спрашиваем не обо всём: сначала дорогие и новые траты, остальное — только чтобы блок
не пустовал. Влияние метки считается контрфактически: два прогноза на одном снимке
и одном seed, с прежней меткой и с новой, поэтому разница не тонет в шуме симуляции.
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Obligation, Transaction, User
from app.domain.enums import TxLabel, TxType
from app.modules.forecasting import current_as_of, prepare_snapshot
from app.schemas.forecasts import ForecastRequest
from forecast_core.baseline import DEFAULT_OBLIGATION_CATEGORIES, ForecastResult
from forecast_core.probabilistic import run_monte_carlo
from forecast_core.recurring import merchant_key

LABELABLE_TYPES = frozenset({TxType.EXPENSE, TxType.FEE, TxType.CREDIT_PURCHASE})
QUEUE_DAYS = 14
QUEUE_SIZE = 5
QUEUE_MIN = 3  # меньше — добираем последними тратами, чтобы было что уточнить
LARGE_FACTOR = 3
LARGE_FLOOR_MINOR = 300_000  # 3 000 ₽: ниже «дорогой» трату не считаем
STATS_DAYS = 91
REDUCIBLE_DAYS = 30


class LabelNotApplicableError(ValueError):
    pass


@dataclass(frozen=True)
class QueueItem:
    transaction: Transaction
    reason: str  # large | new | recent


@dataclass(frozen=True)
class Queue:
    items: list[QueueItem]
    reducible_minor: int
    labeled: int


@dataclass(frozen=True)
class Effect:
    before: ForecastResult
    after: ForecastResult


def labelable(tx: Transaction) -> bool:
    return tx.type in LABELABLE_TYPES and tx.amount_minor < 0 and tx.duplicate_of_id is None


def _merchant(tx: Transaction) -> str:
    return " ".join((tx.description or tx.category or "").lower().split())


def build_queue(db: Session, user: User) -> Queue:
    as_of = current_as_of(db, user)
    obligations = list(db.scalars(select(Obligation).where(Obligation.user_id == user.id)))
    calendar_like = set(DEFAULT_OBLIGATION_CATEGORIES) | {o.kind.value for o in obligations}
    # Платежи подтверждённых регулярных обязательств — тоже из календаря.
    linked = {(o.account_id, o.match_key) for o in obligations if o.match_key}

    def in_calendar(tx: Transaction) -> bool:
        if tx.category in calendar_like:
            return True
        key = merchant_key(tx.description, tx.category)
        return (tx.account_id, key) in linked or (None, key) in linked

    spending = [
        tx
        for tx in db.scalars(
            select(Transaction)
            .where(
                Transaction.user_id == user.id,
                Transaction.occurred_at > as_of - timedelta(days=STATS_DAYS),
                Transaction.occurred_at <= as_of,
            )
            .order_by(Transaction.occurred_at, Transaction.id)
        )
        # Платежи из календаря уже обязательны по определению — о них не спрашиваем.
        if labelable(tx) and not in_calendar(tx)
    ]
    typical = median([-tx.amount_minor for tx in spending]) if spending else 0
    large_from = max(LARGE_FLOOR_MINOR, int(typical * LARGE_FACTOR))
    recent_from = as_of - timedelta(days=QUEUE_DAYS)

    seen: set[str] = set()
    flagged: list[QueueItem] = []
    plain: list[QueueItem] = []
    for tx in spending:
        merchant = _merchant(tx)
        is_new = merchant not in seen
        seen.add(merchant)
        if tx.occurred_at < recent_from or tx.label is not None:
            continue
        if -tx.amount_minor >= large_from:
            flagged.append(QueueItem(tx, "large"))
        elif is_new:
            flagged.append(QueueItem(tx, "new"))
        else:
            plain.append(QueueItem(tx, "recent"))

    order = {"large": 0, "new": 1}
    flagged.sort(key=lambda item: (order[item.reason], -item.transaction.occurred_at.timestamp()))
    items = flagged[:QUEUE_SIZE]
    if len(items) < QUEUE_MIN:
        plain.sort(key=lambda item: -item.transaction.occurred_at.timestamp())
        items += plain[: QUEUE_MIN - len(items)]

    reducible_from = as_of - timedelta(days=REDUCIBLE_DAYS)
    return Queue(
        items=items,
        reducible_minor=sum(
            -tx.amount_minor
            for tx in spending
            if tx.label == TxLabel.REDUCIBLE and tx.occurred_at > reducible_from
        ),
        labeled=sum(1 for tx in spending if tx.label is not None),
    )


def set_label(db: Session, user: User, tx: Transaction, label: TxLabel | None) -> Effect:
    """Сохранить метку и посчитать, как она изменила прогноз (на одном seed)."""
    if not labelable(tx):
        raise LabelNotApplicableError(tx.id)
    previous = tx.label
    tx.label = label
    tx.labeled_at = datetime.now(UTC) if label is not None else None
    db.flush()
    prepared = prepare_snapshot(db, user, ForecastRequest())
    old = previous.value if previous is not None else None
    before_history = tuple(
        replace(item, label=old) if item.id == tx.id else item for item in prepared.snapshot.history
    )
    before = run_monte_carlo(replace(prepared.snapshot, history=before_history))
    after = run_monte_carlo(prepared.snapshot)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="transaction_labeled",
            object_type="transaction",
            object_id=tx.id,
            meta={"label": label.value if label else None, "previous": old},
        )
    )
    db.commit()
    db.refresh(tx)
    return Effect(before=before, after=after)
