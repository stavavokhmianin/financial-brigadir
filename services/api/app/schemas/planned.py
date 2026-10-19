"""Контракты эндпоинтов следующих этапов (раздел 22.2).

Схемы зафиксированы сейчас, чтобы клиент (B) и расчётный модуль (C) работали
параллельно. Обработчики отвечают ``501`` до реализации на своём этапе.
"""

import datetime as dt
from datetime import date, datetime, time
from typing import Literal

from pydantic import Field

from app.domain.enums import AlertAction, Coverage, ImportStatus, NotificationMode, Priority
from app.schemas.common import APIModel, Minor, NonNegativeMinor, PositiveMinor

# --- Импорт CSV (этап 2) ---


class ImportIssue(APIModel):
    row: int
    column: str | None
    code: str
    message: str


class ImportResultOut(APIModel):
    import_id: str
    status: ImportStatus
    fingerprint: str = Field(description="SHA-256 файла: повторная загрузка идемпотентна")
    rows_total: int
    rows_imported: int
    rows_duplicate: int
    rows_rejected: int
    column_mapping: dict[str, str]
    preview: list[dict[str, str]]
    issues: list[ImportIssue]


# --- Прогноз и сценарии (этапы 2–3) ---


class ScenarioEvent(APIModel):
    type: Literal["expense", "income_shift", "income_change", "postpone_expense"]
    amount_minor: PositiveMinor | None = None
    date: dt.date | None = None
    shift_days: int | None = Field(default=None, ge=-31, le=31)
    target_id: str | None = Field(default=None, description="Доход или обязательство")


class ForecastRequest(APIModel):
    account_ids: list[str] | None = Field(default=None, description="По умолчанию все счета")
    horizon_days: int = Field(default=30, ge=1, le=90)
    reserve_minor: NonNegativeMinor = 500_000
    timezone: str = "Europe/Moscow"
    scenario: ScenarioEvent | None = None


class ForecastPointOut(APIModel):
    day: date
    p10_minor: Minor
    p50_minor: Minor
    p90_minor: Minor
    risk_probability: float | None = Field(ge=0, le=1)


class ForecastQuality(APIModel):
    coverage: Coverage
    confidence: Literal["insufficient", "illustrative", "calibrated"] = Field(
        description="Вероятности не считаются реальными, пока модель не откалибрована"
    )


class ForecastOut(APIModel):
    forecast_id: str
    data_as_of: datetime
    horizon_days: int
    model_version: str
    quality: ForecastQuality
    baseline_risk: float | None = Field(ge=0, le=1)
    scenario_risk: float | None = Field(ge=0, le=1)
    risk_date: date | None
    risk_drivers: list[str]
    points: list[ForecastPointOut]


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
