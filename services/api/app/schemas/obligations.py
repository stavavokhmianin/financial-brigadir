import datetime as dt
from datetime import date, datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from app.domain.enums import ObligationKind, ObligationStatus, Priority, Recurrence
from app.schemas.common import APIModel, PositiveMinor


class ObligationOut(APIModel):
    id: str
    account_id: str | None
    kind: ObligationKind
    title: str
    amount_minor: PositiveMinor = Field(description="Сумма списания, положительная")
    amount_min_minor: PositiveMinor | None
    amount_max_minor: PositiveMinor | None
    due_date: date = Field(description="Ближайшая дата платежа")
    recurrence: Recurrence
    recurrence_day: int | None
    priority: Priority
    status: ObligationStatus
    confidence: float
    movable: bool
    source_kind: str | None = Field(description="Откуда событие: synthetic, csv, manual…")
    created_at: datetime


class ObligationOccurrence(APIModel):
    obligation_id: str
    date: dt.date
    title: str
    amount_minor: PositiveMinor
    status: ObligationStatus
    priority: Priority


class ObligationsOut(APIModel):
    items: list[ObligationOut]
    calendar: list[ObligationOccurrence] = Field(
        description="Все платежи в окне [date_from, date_to] с учётом повторяемости"
    )


class ObligationCreate(APIModel):
    title: str = Field(min_length=1, max_length=120)
    kind: ObligationKind = ObligationKind.MANUAL
    amount_minor: PositiveMinor
    amount_min_minor: PositiveMinor | None = None
    amount_max_minor: PositiveMinor | None = None
    due_date: date
    recurrence: Recurrence = Recurrence.NONE
    recurrence_day: int | None = Field(default=None, ge=1, le=31)
    account_id: str | None = None
    priority: Priority = Priority.CRITICAL
    movable: bool = False

    @model_validator(mode="after")
    def _check_ranges(self) -> Self:
        low, high = self.amount_min_minor, self.amount_max_minor
        if (low is None) != (high is None):
            raise ValueError("диапазон суммы задаётся парой amount_min_minor/amount_max_minor")
        if low is not None and high is not None and not low <= self.amount_minor <= high:
            raise ValueError("amount_minor должен лежать в диапазоне [min, max]")
        if self.recurrence_day is not None and self.recurrence != Recurrence.MONTHLY:
            raise ValueError("recurrence_day используется только для monthly")
        return self


class ObligationPatch(APIModel):
    """Подтверждение предполагаемого платежа, отмена или правка (раздел 7.4)."""

    status: Literal["confirmed", "canceled"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    amount_minor: PositiveMinor | None = None
    amount_min_minor: PositiveMinor | None = None
    amount_max_minor: PositiveMinor | None = None
    due_date: date | None = None
    priority: Priority | None = None
    movable: bool | None = None
