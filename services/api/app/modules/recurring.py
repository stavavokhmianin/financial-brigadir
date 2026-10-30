"""Регулярные платежи (FR-11, ADR-0007 этап B): кандидаты, подтверждение, отказ.

Кандидат — повторение из выписки, которого ещё нет в календаре. В обязательство он
превращается только по подтверждению пользователя; после этого его платежи выходят из
модели повседневных трат (forecasting.prepare_snapshot), и прогноз не считает их дважды.
Отклонённый кандидат запоминается и больше не предлагается.
"""

from dataclasses import dataclass
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Obligation, RecurringDecision, Transaction, User
from app.domain.enums import ObligationKind, ObligationStatus, Priority, Recurrence
from app.domain.ids import new_id
from app.modules.forecasting import current_as_of, prepare_snapshot
from app.schemas.forecasts import ForecastRequest
from forecast_core import HistoricalTransaction
from forecast_core.baseline import ForecastResult
from forecast_core.probabilistic import run_monte_carlo
from forecast_core.recurring import (
    WINDOW_DAYS,
    RecurringCandidate,
    detect_recurring,
    merchant_key,
)

MIN_CONFIDENCE = 0.6
SHOWN = 3
DAY_TOLERANCE = 3
AMOUNT_TOLERANCE = 0.2
KINDS = {kind.value for kind in ObligationKind}


class CandidateNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class Confirmed:
    obligation: Obligation
    before: ForecastResult
    after: ForecastResult


def _covered(candidate: RecurringCandidate, obligations: list[Obligation]) -> bool:
    """Повторение уже в календаре: по получателю, названию или дню и сумме."""
    for o in obligations:
        same_account = o.account_id in (None, candidate.account_id)
        if not same_account:
            continue
        if candidate.merchant in (o.match_key, merchant_key(o.title, None)):
            return True
        low = (o.amount_min_minor or o.amount_minor) * (1 - AMOUNT_TOLERANCE)
        high = (o.amount_max_minor or o.amount_minor) * (1 + AMOUNT_TOLERANCE)
        if not low <= candidate.amount_minor <= high:
            continue
        if candidate.period == "monthly" and o.recurrence == Recurrence.MONTHLY:
            day = o.recurrence_day or o.due_date.day
            distance = abs(day - candidate.anchor)
            if min(distance, 31 - distance) <= DAY_TOLERANCE:
                return True
        if candidate.period == "weekly" and o.recurrence == Recurrence.WEEKLY:
            if o.due_date.weekday() == candidate.anchor:
                return True
    return False


def candidates(db: Session, user: User) -> list[RecurringCandidate]:
    as_of = current_as_of(db, user)
    tz = ZoneInfo(user.timezone)
    rows = db.scalars(
        select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.occurred_at > as_of - timedelta(days=WINDOW_DAYS + 2),
            Transaction.occurred_at <= as_of,
            Transaction.duplicate_of_id.is_(None),
        )
    )
    history = [
        HistoricalTransaction(
            id=t.id,
            account_id=t.account_id,
            occurred_at=t.occurred_at,
            amount_minor=t.amount_minor,
            type=t.type,
            status=t.status,
            category=t.category,
            description=t.description,
        )
        for t in rows
    ]
    obligations = list(
        db.scalars(
            select(Obligation).where(
                Obligation.user_id == user.id, Obligation.status != ObligationStatus.CANCELED
            )
        )
    )
    decided = set(
        db.scalars(select(RecurringDecision.key).where(RecurringDecision.user_id == user.id))
    )
    found = detect_recurring(history, as_of.astimezone(tz).date(), tz)
    return [
        c
        for c in found
        if c.confidence >= MIN_CONFIDENCE and c.key not in decided and not _covered(c, obligations)
    ][:SHOWN]


def _find(db: Session, user: User, key: str) -> RecurringCandidate:
    candidate = next((c for c in candidates(db, user) if c.key == key), None)
    if candidate is None:
        raise CandidateNotFoundError(key)
    return candidate


def confirm(db: Session, user: User, key: str) -> Confirmed:
    """Кандидат → обязательство; прогноз до и после на одном seed."""
    candidate = _find(db, user, key)
    request = ForecastRequest()
    before = run_monte_carlo(prepare_snapshot(db, user, request).snapshot)
    if candidate.category in KINDS:
        kind = ObligationKind(candidate.category)
    else:
        kind = (
            ObligationKind.SUBSCRIPTION if candidate.period == "monthly" else ObligationKind.MANUAL
        )
    ranged = candidate.amount_min_minor < candidate.amount_max_minor
    obligation = Obligation(
        id=new_id("obl"),
        user_id=user.id,
        account_id=candidate.account_id,
        source_id=None,
        kind=kind,
        title=candidate.title[:120],
        amount_minor=candidate.amount_minor,
        amount_min_minor=candidate.amount_min_minor if ranged else None,
        amount_max_minor=candidate.amount_max_minor if ranged else None,
        due_date=candidate.next_day,
        recurrence=Recurrence(candidate.period),
        recurrence_day=candidate.anchor if candidate.period == "monthly" else None,
        priority=Priority.NORMAL,
        status=ObligationStatus.CONFIRMED,
        confidence=candidate.confidence,
        movable=False,
        match_key=candidate.merchant,
    )
    db.add(obligation)
    db.add(
        RecurringDecision(
            user_id=user.id, key=key, decision="confirmed", obligation_id=obligation.id
        )
    )
    db.add(
        AuditEvent(
            user_id=user.id,
            action="recurring_confirmed",
            object_type="obligation",
            object_id=obligation.id,
            meta={"period": candidate.period, "occurrences": candidate.occurrences},
        )
    )
    db.flush()
    after = run_monte_carlo(prepare_snapshot(db, user, request).snapshot)
    db.commit()
    db.refresh(obligation)
    return Confirmed(obligation, before, after)


def reject(db: Session, user: User, key: str) -> None:
    _find(db, user, key)
    db.merge(RecurringDecision(user_id=user.id, key=key, decision="rejected"))
    db.add(AuditEvent(user_id=user.id, action="recurring_rejected", meta={"key": key}))
    db.commit()
