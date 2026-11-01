"""Нейтральный контракт банковского/Open Banking коннектора."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from financial_sdk.models import FinancialData
from forecast_core import (
    AccountSnapshot,
    AccountType,
    Coverage,
    HistoricalTransaction,
    TxStatus,
    TxType,
)


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
        self,
        account_id: str,
        since: date,
        until: date,
        cursor: str | None = None,
    ) -> SourcePage: ...

    async def get_balances(self, account_id: str) -> SourceBalance: ...

    async def revoke_access(self, consent: ConsentToken) -> None: ...


@dataclass(frozen=True, slots=True)
class OpenBankingAdapter:
    """Собирает страницы произвольного BankConnector в FinancialData."""

    connector: BankConnector
    consent: ConsentToken
    since: date
    until: date
    timezone: str = "UTC"

    async def load(self) -> FinancialData:
        source_accounts = await self.connector.list_accounts(self.consent)
        accounts: list[AccountSnapshot] = []
        transactions: list[HistoricalTransaction] = []
        partial = False
        moments: list[datetime] = []
        for source in source_accounts:
            balance = await self.connector.get_balances(source.external_id)
            moments.append(balance.as_of)
            account_type = AccountType(source.type)
            accounts.append(
                AccountSnapshot(
                    id=source.external_id,
                    type=account_type,
                    currency=source.currency,
                    balance_minor=balance.available_minor,
                    data_as_of=balance.as_of,
                    is_liquid=account_type not in {AccountType.CREDIT_CARD, AccountType.DEPOSIT},
                    blocked_minor=balance.blocked_minor,
                )
            )
            cursor: str | None = None
            while True:
                page = await self.connector.list_transactions(
                    source.external_id,
                    self.since,
                    self.until,
                    cursor,
                )
                partial = partial or page.is_partial
                transactions.extend(
                    HistoricalTransaction(
                        id=item.external_id,
                        account_id=source.external_id,
                        occurred_at=item.occurred_at,
                        amount_minor=item.amount_minor,
                        type=TxType(item.type),
                        status=TxStatus(item.status),
                        category=item.category,
                        description=item.description,
                    )
                    for item in page.items
                )
                cursor = page.next_cursor
                if cursor is None:
                    break
        if not accounts:
            raise ValueError("коннектор не вернул ни одного счёта")
        return FinancialData(
            as_of=min(moments),
            timezone=self.timezone,
            accounts=tuple(accounts),
            transactions=tuple(transactions),
            coverage=Coverage.PARTIAL if partial else Coverage.FULL,
            currency=accounts[0].currency,
        )
