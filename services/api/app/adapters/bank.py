"""Контракт банковского адаптера (раздел 22.4).

``ConsentToken`` — абстракция, а не реальный токен банка. Живой коннектор
допускается только после официального доступа и описания протокола; пароли
интернет-банка никогда не вводятся.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ConsentToken:
    consent_id: str
    scopes: tuple[str, ...]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class SourceAccount:
    external_id: str
    name: str
    type: str
    currency: str


@dataclass(frozen=True, slots=True)
class SourceTransaction:
    external_id: str
    occurred_at: datetime
    booked_at: datetime | None
    amount_minor: int
    currency: str
    status: str
    description: str | None
    type: str = "expense"
    category: str | None = None


@dataclass(frozen=True, slots=True)
class SourcePage:
    items: tuple[SourceTransaction, ...]
    next_cursor: str | None
    is_partial: bool = False


@dataclass(frozen=True, slots=True)
class SourceBalance:
    account_external_id: str
    available_minor: int
    blocked_minor: int
    as_of: datetime


class BankConnector(Protocol):
    async def list_accounts(self, consent: ConsentToken) -> list[SourceAccount]: ...

    async def list_transactions(
        self, account_id: str, since: date, until: date, cursor: str | None = None
    ) -> SourcePage: ...

    async def get_balances(self, account_id: str) -> SourceBalance: ...

    async def revoke_access(self, consent: ConsentToken) -> None: ...
