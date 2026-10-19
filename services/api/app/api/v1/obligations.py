from datetime import date, timedelta

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.errors import APIError, error_responses, not_found
from app.db.models import Account, AuditEvent, Obligation
from app.domain.enums import ObligationStatus
from app.domain.ids import new_id
from app.schemas.obligations import (
    ObligationCreate,
    ObligationOccurrence,
    ObligationOut,
    ObligationsOut,
)
from forecast_core.calendar import occurrences

router = APIRouter(prefix="/obligations", tags=["obligations"])

MAX_WINDOW_DAYS = 366


def _out(obligation: Obligation) -> ObligationOut:
    return ObligationOut.model_validate(obligation)


@router.get(
    "",
    operation_id="listObligations",
    summary="Обязательства и календарь платежей в окне дат",
    responses=error_responses(400, 401),
)
def list_obligations(
    user: CurrentUser,
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    include_canceled: bool = False,
) -> ObligationsOut:
    start = date_from or date.today()  # noqa: DTZ011 — окно по умолчанию, не расчёт
    end = date_to or start + timedelta(days=30)
    if end < start or (end - start).days > MAX_WINDOW_DAYS:
        raise APIError(
            status.HTTP_400_BAD_REQUEST, "bad_window", "Окно дат должно быть от 0 до 366 дней"
        )
    query = (
        select(Obligation)
        .where(Obligation.user_id == user.id)
        .options(selectinload(Obligation.source))
        .order_by(Obligation.due_date, Obligation.id)
    )
    if not include_canceled:
        query = query.where(Obligation.status != ObligationStatus.CANCELED)
    items = db.scalars(query).all()
    calendar = [
        ObligationOccurrence(
            obligation_id=o.id,
            date=day,
            title=o.title,
            amount_minor=o.amount_minor,
            status=o.status,
            priority=o.priority,
        )
        for o in items
        if o.status != ObligationStatus.CANCELED
        for day in occurrences(o.due_date, o.recurrence, start, end, o.recurrence_day)
    ]
    calendar.sort(key=lambda c: (c.date, c.obligation_id))
    return ObligationsOut(items=[_out(o) for o in items], calendar=calendar)


@router.post(
    "",
    operation_id="createObligation",
    summary="Ручное обязательство (FR-03): подтверждено пользователем",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 404),
)
def create_obligation(body: ObligationCreate, user: CurrentUser, db: DbSession) -> ObligationOut:
    if body.account_id is not None:
        owned = db.scalar(
            select(Account.id).where(Account.id == body.account_id, Account.user_id == user.id)
        )
        if owned is None:
            raise not_found("Счёт")
    obligation = Obligation(
        id=new_id("obl"),
        user_id=user.id,
        account_id=body.account_id,
        kind=body.kind,
        title=body.title,
        amount_minor=body.amount_minor,
        amount_min_minor=body.amount_min_minor,
        amount_max_minor=body.amount_max_minor,
        due_date=body.due_date,
        recurrence=body.recurrence,
        recurrence_day=body.recurrence_day,
        priority=body.priority,
        status=ObligationStatus.CONFIRMED,
        confidence=1.0,
        movable=body.movable,
    )
    db.add(obligation)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="obligation_created",
            object_type="obligation",
            object_id=obligation.id,
        )
    )
    db.commit()
    db.refresh(obligation)
    return _out(obligation)
