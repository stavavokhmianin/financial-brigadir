from datetime import date, datetime
from typing import Self

from pydantic import Field, model_validator

from app.domain.enums import IncomeKind, Recurrence
from app.schemas.common import APIModel, PositiveMinor


class IncomeOut(APIModel):
    id: str
    account_id: str | None
    kind: IncomeKind
    title: str
    date_from: date = Field(description="Самая ранняя ожидаемая дата поступления")
    date_to: date = Field(description="Самая поздняя дата (задержка зарплаты, US-05)")
    amount_min_minor: PositiveMinor
    amount_max_minor: PositiveMinor
    probability: float = Field(ge=0, le=1)
    confirmed: bool
    recurrence: Recurrence
    canceled: bool
    source_kind: str
    created_at: datetime


class IncomeOccurrence(APIModel):
    income_id: str
    date_from: date
    date_to: date
    title: str
    amount_min_minor: PositiveMinor
    amount_max_minor: PositiveMinor
    confirmed: bool
    probability: float


class IncomesOut(APIModel):
    items: list[IncomeOut]
    calendar: list[IncomeOccurrence] = Field(
        description="Ожидаемые поступления в окне [date_from, date_to] с учётом повторяемости"
    )


def _check_window(date_from: date | None, date_to: date | None) -> None:
    if date_from and date_to and date_to < date_from:
        raise ValueError("date_to раньше date_from")
    if date_from and date_to and (date_to - date_from).days > 31:
        raise ValueError("окно поступления не длиннее 31 дня")


class IncomeCreate(APIModel):
    title: str = Field(min_length=1, max_length=120)
    kind: IncomeKind = IncomeKind.SALARY
    amount_minor: PositiveMinor = Field(description="Ожидаемая сумма")
    amount_min_minor: PositiveMinor | None = Field(default=None, description="Если сумма плавает")
    amount_max_minor: PositiveMinor | None = None
    date_from: date
    date_to: date | None = Field(default=None, description="По умолчанию равна date_from")
    recurrence: Recurrence = Recurrence.MONTHLY
    confirmed: bool = True
    probability: float | None = Field(
        default=None, ge=0, le=1, description="По умолчанию 1 для подтверждённого, 0.7 иначе"
    )
    account_id: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        _check_window(self.date_from, self.date_to)
        low, high = self.amount_min_minor, self.amount_max_minor
        if (low is None) != (high is None):
            raise ValueError("диапазон суммы задаётся парой amount_min_minor/amount_max_minor")
        if low is not None and high is not None and not low <= self.amount_minor <= high:
            raise ValueError("amount_minor должен лежать в диапазоне [min, max]")
        return self


class IncomePatch(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    date_from: date | None = None
    date_to: date | None = None
    amount_min_minor: PositiveMinor | None = None
    amount_max_minor: PositiveMinor | None = None
    probability: float | None = Field(default=None, ge=0, le=1)
    confirmed: bool | None = None
    canceled: bool | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        _check_window(self.date_from, self.date_to)
        return self
