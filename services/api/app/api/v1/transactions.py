import base64
import binascii
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import and_, or_, select

from app.api.deps import CurrentUser, DbSession
from app.core.errors import APIError, error_responses, not_found
from app.db.models import Account, AuditEvent, Transaction
from app.domain.enums import TxStatus, TxType
from app.modules.dedup import pending_duplicates, resolve
from app.modules.feedback import LabelNotApplicableError, set_label
from app.schemas.transactions import (
    DuplicatePair,
    DuplicateResolution,
    DuplicatesOut,
    ForecastGlance,
    LabelEffectOut,
    TransactionLabelIn,
    TransactionLabelOut,
    TransactionOut,
    TransactionsPage,
)
from forecast_core.baseline import ForecastResult

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _encode_cursor(tx: Transaction) -> str:
    raw = f"{tx.occurred_at.isoformat()}|{tx.id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        moment, tx_id = raw.split("|", 1)
        parsed = datetime.fromisoformat(moment)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise APIError(status.HTTP_400_BAD_REQUEST, "bad_cursor", "Некорректный cursor") from exc
    if parsed.tzinfo is None:
        raise APIError(status.HTTP_400_BAD_REQUEST, "bad_cursor", "Некорректный cursor")
    return parsed, tx_id


@router.get(
    "",
    operation_id="listTransactions",
    summary="Операции: фильтрация и курсорная пагинация (новые сверху)",
    responses=error_responses(400, 401, 404),
)
def list_transactions(
    user: CurrentUser,
    db: DbSession,
    account_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    type: Annotated[TxType | None, Query()] = None,
    status_: Annotated[TxStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> TransactionsPage:
    query = select(Transaction).where(Transaction.user_id == user.id)
    if account_id is not None:
        owned = db.scalar(
            select(Account.id).where(Account.id == account_id, Account.user_id == user.id)
        )
        if owned is None:
            raise not_found("Счёт")
        query = query.where(Transaction.account_id == account_id)
    # Границы дат — UTC-сутки; пользовательская таймзона применяется на клиенте.
    if date_from is not None:
        query = query.where(Transaction.occurred_at >= datetime.combine(date_from, time(), UTC))
    if date_to is not None:
        end = datetime.combine(date_to + timedelta(days=1), time(), UTC)
        query = query.where(Transaction.occurred_at < end)
    if type is not None:
        query = query.where(Transaction.type == type)
    if status_ is not None:
        query = query.where(Transaction.status == status_)
    if cursor is not None:
        moment, tx_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                Transaction.occurred_at < moment,
                and_(Transaction.occurred_at == moment, Transaction.id < tx_id),
            )
        )
    rows = db.scalars(
        query.order_by(Transaction.occurred_at.desc(), Transaction.id.desc()).limit(limit + 1)
    ).all()
    items = rows[:limit]
    next_cursor = _encode_cursor(items[-1]) if len(rows) > limit else None
    return TransactionsPage(
        items=[TransactionOut.model_validate(t) for t in items], next_cursor=next_cursor
    )


@router.get(
    "/duplicates",
    operation_id="listProbableDuplicates",
    summary="Вероятные дубли, которые нужно подтвердить или отклонить (FR-08)",
    responses=error_responses(401),
)
def list_duplicates(user: CurrentUser, db: DbSession) -> DuplicatesOut:
    return DuplicatesOut(
        items=[
            DuplicatePair(
                transaction=TransactionOut.model_validate(tx),
                original=TransactionOut.model_validate(original),
                reason=tx.review_reason,
            )
            for tx, original in pending_duplicates(db, user)
        ]
    )


@router.post(
    "/{transaction_id}/duplicate-resolution",
    operation_id="resolveDuplicate",
    summary="Решение пользователя: дубль (исключить из модели) или разные операции",
    responses=error_responses(400, 401, 404),
)
def resolve_duplicate(
    transaction_id: str, body: DuplicateResolution, user: CurrentUser, db: DbSession
) -> TransactionOut:
    tx = db.scalar(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id)
    )
    if tx is None:
        raise not_found("Операция")
    if tx.duplicate_candidate_id is None:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            "not_a_candidate",
            "Операция не помечена как вероятный дубль",
        )
    resolve(tx, body.decision)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="duplicate_resolved",
            object_type="transaction",
            object_id=tx.id,
            meta={"decision": body.decision},
        )
    )
    db.commit()
    db.refresh(tx)
    return TransactionOut.model_validate(tx)


def _glance(result: ForecastResult) -> ForecastGlance:
    return ForecastGlance(
        risk_level=result.risk_level,
        min_balance_minor=result.min_p50_minor,
        min_balance_date=result.min_p50_day,
        pessimistic_min_minor=result.min_p10_minor,
        excluded_one_off=result.spending.excluded_one_off,
    )


@router.put(
    "/{transaction_id}/label",
    operation_id="setTransactionLabel",
    summary="Метка траты от пользователя и как она изменила прогноз (ADR-0007)",
    responses=error_responses(400, 401, 404),
)
def put_label(
    transaction_id: str, body: TransactionLabelIn, user: CurrentUser, db: DbSession
) -> TransactionLabelOut:
    tx = db.scalar(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id)
    )
    if tx is None:
        raise not_found("Операция")
    try:
        effect = set_label(db, user, tx, body.label)
    except LabelNotApplicableError:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            "label_not_applicable",
            "Метку можно поставить только на трату",
        ) from None
    before, after = _glance(effect.before), _glance(effect.after)
    return TransactionLabelOut(
        transaction=TransactionOut.model_validate(tx),
        effect=LabelEffectOut(
            before=before,
            after=after,
            changed=(before.risk_level, before.min_balance_minor, before.pessimistic_min_minor)
            != (after.risk_level, after.min_balance_minor, after.pessimistic_min_minor),
        ),
    )
