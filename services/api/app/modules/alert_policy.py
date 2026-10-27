"""Alert Policy Engine (разделы 7.7, 10, 23.4; FR-22–FR-24).

Чистая функция: риск из прогноза + настройки + история предупреждений + время
→ ``send`` / ``defer`` / ``suppress`` с причиной. Порядок правил соответствует
примеру из 10.2:

    IF probability_of_gap >= threshold AND forecast_quality != insufficient
       AND actionable_recommendation_exists AND notification_cooldown_passed
    THEN show_warning_with_explanation ELSE suppress_or_defer

Пороги — стартовые продуктовые значения, их уточняет эксперимент (10.1, 15.3).
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

EVENT_TYPE = "reserve_risk"
ACTIONABLE_HORIZON_DAYS = 14  # раздел 23.4: существенные риски на горизонте до 14 дней
REPEAT_WINDOW = timedelta(days=7)
REPEAT_DATE_TOLERANCE_DAYS = 3
REPEAT_SHORTFALL_CHANGE = 0.2  # изменение дефицита меньше 20 % — «без существенного изменения»
REPEAT_SHORTFALL_FLOOR_MINOR = 100_000  # и меньше 1 000 ₽


@dataclass(frozen=True)
class RiskSignal:
    level: str  # low | medium | high
    risk_date: date | None
    shortfall_minor: int
    today: date  # день прогноза в часовом поясе пользователя
    critical_payment: bool  # до даты риска есть обязательный платёж
    stale: bool
    insufficient: bool


@dataclass(frozen=True)
class Preferences:
    mode: str  # quiet | smart | active
    quiet_start: time | None
    quiet_end: time | None
    max_noncritical_per_week: int
    disabled_types: tuple[str, ...]


@dataclass(frozen=True)
class PastAlert:
    action: str
    priority: str
    risk_date: date | None
    shortfall_minor: int | None
    created_at: datetime


@dataclass(frozen=True)
class Decision:
    action: str  # send | defer | suppress
    reason: str
    priority: str  # critical | normal
    event_key: str = EVENT_TYPE


def in_quiet_hours(local_now: time, start: time | None, end: time | None) -> bool:
    if start is None or end is None or start == end:
        return False
    if start < end:
        return start <= local_now < end
    return local_now >= start or local_now < end  # интервал через полночь (22:00–08:00)


def _is_repeat(signal: RiskSignal, last: PastAlert) -> bool:
    if last.risk_date is None or signal.risk_date is None:
        return False
    if abs((signal.risk_date - last.risk_date).days) > REPEAT_DATE_TOLERANCE_DAYS:
        return False
    before = last.shortfall_minor or 0
    change = abs(signal.shortfall_minor - before)
    return change < max(REPEAT_SHORTFALL_FLOOR_MINOR, REPEAT_SHORTFALL_CHANGE * before)


def decide(
    signal: RiskSignal,
    prefs: Preferences,
    history: list[PastAlert],
    now_utc: datetime,
    local_now: time,
) -> Decision | None:
    """``None`` — предупреждать не о чем (риска нет); иначе решение с причиной."""
    if signal.level == "low" or signal.risk_date is None:
        return None
    critical = signal.level == "high" and signal.critical_payment
    priority = "critical" if critical else "normal"

    def result(action: str, reason: str) -> Decision:
        return Decision(action, reason, priority)

    if EVENT_TYPE in prefs.disabled_types:
        return result("suppress", "type_disabled")
    if signal.insufficient:
        return result("suppress", "insufficient_data")
    if signal.stale:
        # 10.2: при устаревших данных сначала предложить обновить, а не пугать числом.
        return result("defer", "stale_data")
    if (signal.risk_date - signal.today).days > ACTIONABLE_HORIZON_DAYS:
        return result("defer", "far_horizon")
    if prefs.mode == "quiet" and not critical:
        return result("suppress", "mode_quiet")
    if prefs.mode == "smart" and signal.level == "medium" and not signal.critical_payment:
        return result("suppress", "mode_smart_minor")

    sent = [a for a in history if a.action == "send" and now_utc - a.created_at < REPEAT_WINDOW]
    if sent and _is_repeat(signal, max(sent, key=lambda a: a.created_at)):
        return result("suppress", "repeat_without_change")
    if not critical:
        weekly = [a for a in sent if a.priority == "normal"]
        if len(weekly) >= prefs.max_noncritical_per_week:
            return result("suppress", "weekly_limit")
    if in_quiet_hours(local_now, prefs.quiet_start, prefs.quiet_end):
        return result("defer", "quiet_hours")
    return result("send", "new_risk" if not sent else "risk_changed")
