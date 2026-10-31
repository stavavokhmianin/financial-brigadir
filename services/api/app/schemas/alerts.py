from datetime import date, datetime, time
from typing import Literal

from pydantic import Field

from app.domain.enums import AlertAction, NotificationMode, Priority
from app.schemas.common import APIModel, NonNegativeMinor


class AlertOut(APIModel):
    id: str
    action: AlertAction = Field(
        description="send — показано; defer — отложено; suppress — подавлено"
    )
    priority: Priority
    reason: str = Field(description="Код причины решения")
    reason_text: str = Field(description="Причина простыми словами")
    message: str | None = Field(description="Текст предупреждения по шаблону 11.4")
    risk_date: date | None
    shortfall_minor: NonNegativeMinor | None
    forecast_id: str | None
    feedback: str | None
    read_at: datetime | None
    created_at: datetime


class AlertsOut(APIModel):
    items: list[AlertOut]


class AlertsReadRequest(APIModel):
    """Идентификаторы событий, которые клиент действительно показал в открытой панели."""

    alert_ids: list[str] = Field(min_length=1, max_length=100)


class AlertsReadOut(APIModel):
    """Результат открытия ленты: только показанные события становятся прочитанными."""

    read_count: int
    read_at: datetime


class AlertFeedback(APIModel):
    """Отзыв и точечное управление уведомлениями."""

    feedback: Literal["useful", "not_relevant", "disable_type", "disable_event"]


class AlertAnalyticsOut(APIModel):
    """Метрики уведомлений (раздел 4.4): нагрузка, причины подавления, полезность."""

    total_decisions: int
    by_action: dict[str, int]
    by_reason: dict[str, int]
    feedback: dict[str, int]
    useful_share: float | None = Field(description="Доля «полезно» среди отзывов")
    disable_rate: float | None = Field(description="Доля отключений среди отзывов")
    sent_last_7_days: int


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
