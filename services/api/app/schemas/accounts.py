from datetime import datetime
from typing import Self

from pydantic import Field, model_validator

from app.domain.enums import AccountType, DataSourceKind
from app.schemas.common import APIModel, Currency, DataQuality, Minor, NonNegativeMinor


class SourceOut(APIModel):
    id: str
    kind: DataSourceKind
    label: str
    data_as_of: datetime | None
    is_partial: bool


class AccountOut(APIModel):
    id: str
    name: str
    bank_name: str | None
    type: AccountType
    currency: Currency
    available_balance_minor: Minor = Field(
        description="Для кредитной карты отрицательное значение — долг"
    )
    credit_limit_minor: NonNegativeMinor | None
    blocked_minor: NonNegativeMinor
    is_liquid: bool = Field(description="Учитывается ли счёт в свободных средствах")
    updated_at: datetime
    source: SourceOut | None


class AccountsOut(APIModel):
    items: list[AccountOut]
    liquid_balance_minor: Minor = Field(
        description="Свободные собственные средства: без кредитных лимитов, депозитов и блокировок"
    )
    data_quality: DataQuality


class AccountCreate(APIModel):
    name: str = Field(min_length=1, max_length=120)
    type: AccountType
    available_balance_minor: Minor
    currency: Currency = "RUB"
    bank_name: str | None = Field(default=None, max_length=120)
    credit_limit_minor: NonNegativeMinor | None = None
    is_liquid: bool | None = Field(
        default=None, description="По умолчанию false для кредитной карты и вклада"
    )

    @model_validator(mode="after")
    def _check_type_rules(self) -> Self:
        if self.type == AccountType.CREDIT_CARD and self.credit_limit_minor is None:
            raise ValueError("для кредитной карты нужен credit_limit_minor")
        if self.type != AccountType.CREDIT_CARD and self.credit_limit_minor is not None:
            raise ValueError("credit_limit_minor допустим только для кредитной карты")
        if self.type == AccountType.CREDIT_CARD and self.is_liquid:
            raise ValueError("кредитный лимит не является свободными средствами")
        return self


class AccountPatch(APIModel):
    """Обновление остатка или названия вручную (FR-03): дата актуальности = сейчас."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    available_balance_minor: Minor | None = None
    blocked_minor: NonNegativeMinor | None = None
    credit_limit_minor: NonNegativeMinor | None = None
    is_liquid: bool | None = None
