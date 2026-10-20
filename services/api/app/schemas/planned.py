"""Контракты эндпоинтов следующих этапов (раздел 22.2).

Схемы зафиксированы сейчас, чтобы клиент (B) и расчётный модуль (C) работали
параллельно. Обработчики отвечают ``501`` до реализации на своём этапе.
"""

from typing import Literal

from app.schemas.common import APIModel

# --- Мок банковского подключения (22.4) ---


class BankMockSyncRequest(APIModel):
    scenario: Literal["ok", "consent_expired", "partial", "network_error", "duplicates"] = "ok"


class BankMockSyncOut(APIModel):
    status: Literal["synced", "partial", "failed"]
    accounts_seen: int
    transactions_new: int
    transactions_duplicate: int
    message: str
