import datetime as dt
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.enums import CategorySource, TxLabel, TxStatus, TxType
from app.schemas.common import APIModel, Currency, Minor


class TransactionOut(APIModel):
    id: str
    account_id: str
    occurred_at: datetime
    booked_at: datetime | None
    amount_minor: Minor = Field(description="Поступление > 0, списание < 0")
    currency: Currency
    type: TxType
    status: TxStatus
    category: str | None
    category_source: CategorySource
    description: str | None
    transfer_group_id: str | None
    related_transaction_id: str | None
    needs_review: bool
    review_reason: str | None
    duplicate_candidate_id: str | None
    duplicate_of_id: str | None = Field(description="Подтверждённый дубль: исключён из модели")
    label: TxLabel | None = Field(
        default=None, description="Метка пользователя: влияет на модель трат, не на баланс"
    )
    user_note: str | None = Field(
        default=None, description="Личный комментарий: хранится отдельно и сам не меняет модель"
    )


class TransactionsPage(APIModel):
    items: list[TransactionOut]
    next_cursor: str | None = Field(description="Передайте в cursor для следующей страницы")


class DuplicatePair(APIModel):
    transaction: TransactionOut = Field(description="Предполагаемый дубль")
    original: TransactionOut
    reason: Literal["same_moment", "cross_source"]


class DuplicatesOut(APIModel):
    items: list[DuplicatePair]


class DuplicateResolution(APIModel):
    decision: Literal["duplicate", "not_duplicate"]


class TransactionLabelIn(APIModel):
    label: TxLabel | None = Field(description="null — снять метку")
    user_note: str | None = Field(default=None, max_length=280)


class ForecastGlance(APIModel):
    """Главное о прогнозе — для сравнения «было / стало»."""

    risk_level: Literal["low", "medium", "high"]
    min_balance_minor: Minor = Field(description="Минимальный остаток, базовый сценарий")
    min_balance_date: dt.date
    pessimistic_min_minor: Minor = Field(description="Минимальный остаток, плохой сценарий")
    excluded_one_off: int = Field(description="Сколько трат исключено как разовые")


class ForecastEffectOut(APIModel):
    before: ForecastGlance
    after: ForecastGlance
    changed: bool = Field(description="Изменились риск или минимальный остаток в сценариях")


class TransactionLabelOut(APIModel):
    transaction: TransactionOut
    effect: ForecastEffectOut


class FeedbackItemOut(APIModel):
    transaction: TransactionOut
    reason: Literal["large", "new", "recent"] = Field(
        description="large — дороже обычного; new — новый получатель; recent — просто недавняя"
    )


class FeedbackOut(APIModel):
    items: list[FeedbackItemOut]
    reducible_30d_minor: Minor = Field(
        description="Траты с меткой «можно сократить» за 30 дней: потенциал, не обещание"
    )
    labeled: int = Field(description="Сколько трат уже размечено")
