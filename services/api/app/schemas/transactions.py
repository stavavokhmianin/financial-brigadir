from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.enums import CategorySource, TxStatus, TxType
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
