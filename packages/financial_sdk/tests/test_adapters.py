import asyncio
from datetime import UTC, date, datetime

import pytest

from financial_sdk import (
    AccountSnapshot,
    AccountType,
    AdapterRegistry,
    ConsentToken,
    CSVTransactionsAdapter,
    InMemoryAdapter,
    NormalizationError,
    OpenBankingAdapter,
    SourceAccount,
    SourceBalance,
    SourcePage,
    SourceTransaction,
    normalize_financial_data,
)

AS_OF = datetime(2026, 10, 31, 12, tzinfo=UTC)


def document() -> dict[str, object]:
    return {
        "as_of": AS_OF.isoformat(),
        "timezone": "Europe/Moscow",
        "coverage": "full",
        "accounts": [
            {
                "id": "main",
                "type": "debit",
                "currency": "RUB",
                "balance_minor": 1_000_000,
                "data_as_of": AS_OF.isoformat(),
            }
        ],
        "transactions": [
            {
                "id": "tx-1",
                "account_id": "main",
                "occurred_at": "2026-10-30T10:00:00+03:00",
                "amount_minor": -12_000,
                "type": "expense",
                "status": "posted",
            }
        ],
    }


def test_normalizer_and_registry_are_storage_agnostic() -> None:
    registry = AdapterRegistry()
    registry.register("memory", InMemoryAdapter)
    loaded = registry.create("memory", source=document()).load()
    assert registry.names() == ("memory",)
    assert loaded.accounts[0].balance_minor == 1_000_000
    assert loaded.transactions[0].amount_minor == -12_000
    with pytest.raises(ValueError, match="уже зарегистрирован"):
        registry.register("memory", InMemoryAdapter)


def test_normalizer_rejects_naive_time_and_unknown_account() -> None:
    bad_time = document()
    bad_time["as_of"] = "2026-10-31T12:00:00"
    with pytest.raises(NormalizationError, match="часовой пояс"):
        normalize_financial_data(bad_time)

    bad_account = document()
    bad_account["transactions"][0]["account_id"] = "other"  # type: ignore[index]
    with pytest.raises(NormalizationError, match="неизвестными account_id"):
        normalize_financial_data(bad_account)


def test_csv_adapter_has_explicit_money_units() -> None:
    account = AccountSnapshot(
        id="card",
        type=AccountType.DEBIT,
        currency="RUB",
        balance_minor=500_000,
        data_as_of=AS_OF,
    )
    loaded = CSVTransactionsAdapter(
        content=(
            "id,occurred_at,amount_minor,type,status,description\n"
            "one,2026-10-30T10:00:00+03:00,-12345,expense,posted,Кофе\n"
        ),
        account=account,
        as_of=AS_OF,
        timezone="Europe/Moscow",
    ).load()
    assert loaded.transactions[0].amount_minor == -12_345
    assert loaded.transactions[0].occurred_at.tzinfo is UTC


class Connector:
    async def list_accounts(self, consent: ConsentToken) -> list[SourceAccount]:
        return [SourceAccount("bank-main", "Карта", "debit", "RUB")]

    async def get_balances(self, account_id: str) -> SourceBalance:
        return SourceBalance(account_id, 2_000_000, 0, AS_OF)

    async def list_transactions(
        self,
        account_id: str,
        since: date,
        until: date,
        cursor: str | None = None,
    ) -> SourcePage:
        return SourcePage(
            (
                SourceTransaction(
                    "bank-tx-1",
                    AS_OF,
                    AS_OF,
                    -50_000,
                    "RUB",
                    "posted",
                    "Магазин",
                ),
            ),
            None,
        )

    async def revoke_access(self, consent: ConsentToken) -> None:
        return None


def test_open_banking_adapter_depends_only_on_protocol() -> None:
    adapter = OpenBankingAdapter(
        connector=Connector(),
        consent=ConsentToken("consent", ("accounts", "transactions"), AS_OF),
        since=date(2026, 10, 1),
        until=date(2026, 10, 31),
        timezone="Europe/Moscow",
    )
    loaded = asyncio.run(adapter.load())
    assert loaded.accounts[0].id == "bank-main"
    assert loaded.transactions[0].description == "Магазин"
    assert loaded.coverage.value == "full"
