"""Контракты эндпоинтов следующих этапов (раздел 22.2).

Схемы зафиксированы сейчас, чтобы клиент (B) и расчётный модуль (C) работали
параллельно. Обработчики отвечают ``501`` до реализации на своём этапе.
"""

from datetime import date, datetime, time
from typing import Literal

from pydantic import Field

from app.domain.enums import AlertAction, NotificationMode, Priority
from app.schemas.common import APIModel, Minor, NonNegativeMinor
from app.schemas.forecasts import ForecastOut, ScenarioEvent

# --- Сравнение сценариев (этап 3) ---


class ScenarioRequest(APIModel):
    base_forecast_id: str
    events: list[ScenarioEvent] = Field(min_length=1, max_length=10)


class ScenarioOut(APIModel):
    scenario_id: str
    base: ForecastOut
    result: ForecastOut
    delta_risk: float | None
    min_balance_delta_minor: Minor


# --- Уведомления ---


class AlertOut(APIModel):
    id: str
    action: AlertAction
    priority: Priority
    reason: str
    risk_date: date | None
    shortfall_minor: NonNegativeMinor | None
    forecast_id: str | None
    created_at: datetime


class AlertsOut(APIModel):
    items: list[AlertOut]


class NotificationSettingsPatch(APIModel):
    mode: NotificationMode | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    max_noncritical_per_week: int | None = Field(default=None, ge=0, le=14)
    disabled_types: list[str] | None = Field(default=None, max_length=20)


class NotificationSettingsOut(APIModel):
    mode: NotificationMode
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    max_noncritical_per_week: int
    disabled_types: list[str]


# --- Мок банковского подключения (22.4) ---


class BankMockSyncRequest(APIModel):
    scenario: Literal["ok", "consent_expired", "partial", "network_error", "duplicates"] = "ok"


class BankMockSyncOut(APIModel):
    status: Literal["synced", "partial", "failed"]
    accounts_seen: int
    transactions_new: int
    transactions_duplicate: int
    message: str
