"""Deterministic synthetic connector. No network and no bank credentials."""

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from app.adapters.bank import (
    ConsentToken,
    SourceAccount,
    SourceBalance,
    SourcePage,
    SourceTransaction,
)
from app.adapters.synthetic import SyntheticDataAdapter

MockScenario = Literal["ok", "consent_expired", "partial", "network_error", "duplicates", "delayed"]
SCOPES = ("accounts", "transactions", "balances")


class BankAccessError(Exception):
    pass


class BankNetworkError(Exception):
    pass


class BankMockConnector:
    def __init__(self, consent: ConsentToken, scenario: MockScenario = "ok") -> None:
        self.consent = consent
        self.scenario = scenario
        self.revoked = False
        self.bundle = SyntheticDataAdapter().load("young_specialist", 901)
        self.as_of = self.bundle.as_of - timedelta(days=2 if scenario == "delayed" else 0)

    def _check(self, scope: str) -> None:
        if (
            self.revoked
            or self.consent.expires_at <= datetime.now(UTC)
            or self.scenario == "consent_expired"
            or scope not in self.consent.scopes
        ):
            raise BankAccessError("consent unavailable")

    async def list_accounts(self, consent: ConsentToken) -> list[SourceAccount]:
        self._check("accounts")
        if consent != self.consent:
            raise BankAccessError("consent mismatch")
        return [
            SourceAccount(a["account_id"], "Учебный банк · " + a["name"], a["type"], a["currency"])
            for a in self.bundle.accounts
        ]

    async def list_transactions(
        self,
        account_id: str,
        since: date,
        until: date,
        cursor: str | None = None,
    ) -> SourcePage:
        self._check("transactions")
        self._account(account_id)
        if self.scenario == "network_error" and cursor is not None:
            raise BankNetworkError("simulated failure on page two")
        records = [
            r
            for r in self.bundle.transactions
            if r["account_id"] == account_id
            and since <= datetime.fromisoformat(r["occurred_at"]).date() <= until
            and datetime.fromisoformat(r["occurred_at"]) <= self.as_of
        ]
        records.sort(key=lambda r: (r["occurred_at"], r["external_id"]))
        if self.scenario == "partial":
            records = records[: len(records) // 2]
        if self.scenario == "duplicates":
            records = records + records[:20]
        offset = int(cursor) if cursor is not None else 0
        if offset < 0 or offset > len(records):
            raise ValueError("invalid cursor")
        items = tuple(
            SourceTransaction(
                r["external_id"],
                datetime.fromisoformat(r["occurred_at"]),
                datetime.fromisoformat(r["booked_at"]) if r.get("booked_at") else None,
                r["amount_minor"],
                r["currency"],
                r["status"],
                r.get("description"),
                r["type"],
                r.get("category"),
            )
            for r in records[offset : offset + 50]
        )
        next_offset = offset + len(items)
        return SourcePage(
            items,
            str(next_offset) if next_offset < len(records) else None,
            self.scenario == "partial",
        )

    def _account(self, account_id: str) -> None:
        if not any(a["account_id"] == account_id for a in self.bundle.accounts):
            raise BankAccessError("unknown account")

    async def get_balances(self, account_id: str) -> SourceBalance:
        self._check("balances")
        self._account(account_id)
        account = next(a for a in self.bundle.accounts if a["account_id"] == account_id)
        delayed_net = sum(
            r["amount_minor"]
            for r in self.bundle.transactions
            if r["account_id"] == account_id
            and datetime.fromisoformat(r["occurred_at"]) > self.as_of
        )
        return SourceBalance(
            account_id, account["balance_minor"] - delayed_net, account["blocked_minor"], self.as_of
        )

    async def revoke_access(self, consent: ConsentToken) -> None:
        if consent != self.consent:
            raise BankAccessError("consent mismatch")
        self.revoked = True
