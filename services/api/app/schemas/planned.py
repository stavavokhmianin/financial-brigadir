"""Контракты эндпоинтов следующих этапов (раздел 22.2).

Схемы зафиксированы сейчас, чтобы клиент (B) и расчётный модуль (C) работали
параллельно. Обработчики отвечают ``501`` до реализации на своём этапе.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.adapters.bank_mock import MockScenario
from app.schemas.common import APIModel

# --- Мок банковского подключения (22.4) ---


class BankMockSyncRequest(APIModel):
    scenario: MockScenario = "ok"


class BankMockSyncOut(APIModel):
    status: Literal["synced", "partial", "failed"]
    accounts_seen: int
    transactions_new: int
    transactions_duplicate: int
    message: str
    data_as_of: datetime
    is_mock: Literal[True] = True


class BankConsentRequest(APIModel):
    accepted: Literal[True]
    scopes: list[Literal["accounts", "transactions", "balances"]] = Field(
        min_length=1, max_length=3
    )
    ttl_hours: int = Field(default=24, ge=1, le=24)


class BankConsentOut(APIModel):
    id: str
    scopes: list[str]
    expires_at: datetime
    revoked_at: datetime | None
    is_mock: Literal[True] = True
