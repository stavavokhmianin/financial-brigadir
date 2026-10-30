import datetime as dt
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel, PositiveMinor
from app.schemas.obligations import ObligationOut
from app.schemas.transactions import ForecastEffectOut


class RecurringCandidateOut(APIModel):
    """Повторение из выписки, которого нет в календаре (FR-11)."""

    id: str = Field(description="Ключ кандидата: счёт, получатель и период")
    title: str
    account_id: str
    category: str | None
    period: Literal["monthly", "weekly"]
    anchor: int = Field(description="День месяца (monthly) или день недели, 0 — понедельник")
    amount_minor: PositiveMinor = Field(description="Типичная сумма списания")
    amount_min_minor: PositiveMinor
    amount_max_minor: PositiveMinor
    occurrences: int = Field(description="Сколько раз встречалось за последние ~200 дней")
    last_date: dt.date
    next_date: dt.date = Field(description="Ожидаемая дата следующего списания")
    confidence: float = Field(
        ge=0,
        le=1,
        description="Насколько регулярно повторялось. Не вероятность — показывать словами",
    )


class RecurringOut(APIModel):
    items: list[RecurringCandidateOut]


class RecurringConfirmOut(APIModel):
    obligation: ObligationOut
    effect: ForecastEffectOut = Field(
        description="Прогноз до и после: платёж в календаре, из повседневных трат убран"
    )
