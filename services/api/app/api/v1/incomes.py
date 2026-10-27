from datetime import date, timedelta

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.errors import APIError, error_responses, not_found
from app.db.models import Account, AuditEvent, IncomeEvent
from app.domain.ids import new_id
from app.schemas.incomes import (
    IncomeCreate,
    IncomeOccurrence,
    IncomeOut,
    IncomePatch,
    IncomesOut,
)
from forecast_core.calendar import occurrences

router = APIRouter(prefix="/incomes", tags=["incomes"])

MAX_WINDOW_DAYS = 366


def _owned(db: DbSession, user_id: str, income_id: str) -> IncomeEvent:
    income = db.scalar(
        select(IncomeEvent).where(IncomeEvent.id == income_id, IncomeEvent.user_id == user_id)
    )
    if income is None:
        raise not_found("Доход")
    return income


@router.get(
    "",
    operation_id="listIncomes",
    summary="Ожидаемые поступления и их календарь в окне дат",
    responses=error_responses(400, 401),
)
def list_incomes(
    user: CurrentUser,
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    include_canceled: bool = False,
) -> IncomesOut:
    start = date_from or date.today()  # noqa: DTZ011 — окно по умолчанию, не расчёт
    end = date_to or start + timedelta(days=30)
    if end < start or (end - start).days > MAX_WINDOW_DAYS:
        raise APIError(
            status.HTTP_400_BAD_REQUEST, "bad_window", "Окно дат должно быть от 0 до 366 дней"
        )
    query = (
        select(IncomeEvent)
        .where(IncomeEvent.user_id == user.id)
        .options(selectinload(IncomeEvent.source))
        .order_by(IncomeEvent.date_from, IncomeEvent.id)
    )
    if not include_canceled:
        query = query.where(IncomeEvent.canceled.is_(False))
    items = db.scalars(query).all()
    calendar: list[IncomeOccurrence] = []
    for income in items:
        if income.canceled:
            continue
        spread = income.date_to - income.date_from
        # Окно поступления (например, 25–28 число) сдвигается вместе с датой начала.
        for day in occurrences(income.date_from, income.recurrence, start - spread, end):
            calendar.append(
                IncomeOccurrence(
                    income_id=income.id,
                    date_from=day,
                    date_to=day + spread,
                    title=income.title,
                    amount_min_minor=income.amount_min_minor,
                    amount_max_minor=income.amount_max_minor,
                    confirmed=income.confirmed,
                    probability=income.probability,
                )
            )
    calendar.sort(key=lambda c: (c.date_from, c.income_id))
    return IncomesOut(items=[IncomeOut.model_validate(i) for i in items], calendar=calendar)


@router.post(
    "",
    operation_id="createIncome",
    summary="Ожидаемый доход вручную (US-01, US-05): дата или окно дат, сумма или диапазон",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 404),
)
def create_income(body: IncomeCreate, user: CurrentUser, db: DbSession) -> IncomeOut:
    if body.account_id is not None:
        owned = db.scalar(
            select(Account.id).where(Account.id == body.account_id, Account.user_id == user.id)
        )
        if owned is None:
            raise not_found("Счёт")
    probability = body.probability
    if probability is None:
        probability = 1.0 if body.confirmed else 0.7
    income = IncomeEvent(
        id=new_id("inc"),
        user_id=user.id,
        account_id=body.account_id,
        kind=body.kind,
        title=body.title,
        date_from=body.date_from,
        date_to=body.date_to or body.date_from,
        amount_min_minor=body.amount_min_minor or body.amount_minor,
        amount_max_minor=body.amount_max_minor or body.amount_minor,
        probability=probability,
        confirmed=body.confirmed,
        recurrence=body.recurrence,
    )
    db.add(income)
    db.add(
        AuditEvent(
            user_id=user.id, action="income_created", object_type="income", object_id=income.id
        )
    )
    db.commit()
    db.refresh(income)
    return IncomeOut.model_validate(income)


@router.patch(
    "/{income_id}",
    operation_id="updateIncome",
    summary="Подтвердить, сдвинуть, изменить или отменить ожидаемый доход",
    responses=error_responses(400, 401, 404),
)
def update_income(income_id: str, body: IncomePatch, user: CurrentUser, db: DbSession) -> IncomeOut:
    income = _owned(db, user.id, income_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(income, field, value)
    if income.date_to < income.date_from:
        raise APIError(status.HTTP_400_BAD_REQUEST, "bad_dates", "date_to раньше date_from")
    if income.amount_min_minor > income.amount_max_minor:
        raise APIError(status.HTTP_400_BAD_REQUEST, "bad_amounts", "Минимум больше максимума")
    if body.confirmed:
        income.probability = max(income.probability, 0.95)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="income_updated",
            object_type="income",
            object_id=income.id,
            meta={"fields": sorted(changes)},
        )
    )
    db.commit()
    db.refresh(income)
    return IncomeOut.model_validate(income)
