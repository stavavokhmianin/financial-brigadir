"""Журнал решений по предупреждениям: политика + шаблон текста + хранение (7.7, 11.4, 23.4)."""

from collections import Counter
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Alert, NotificationSettings, Obligation, User
from app.domain.enums import AlertAction, ObligationStatus, Priority, Recurrence
from app.domain.ids import new_id
from app.modules.alert_policy import (
    EVENT_TYPE,
    Decision,
    PastAlert,
    Preferences,
    RiskSignal,
    decide,
)
from app.modules.explain import day_text, rub
from app.schemas.alerts import AlertAnalyticsOut, AlertOut
from forecast_core.baseline import ForecastResult
from forecast_core.calendar import occurrences

HISTORY_WINDOW = timedelta(days=14)
EXPECTED_RECURRING = "expected_recurring"

REASON_TEXT = {
    "new_risk": "Новый риск нехватки до обязательных платежей",
    "risk_changed": "Риск изменился с прошлого предупреждения",
    "repeat_without_change": "Повтор того же риска без существенных изменений",
    "weekly_limit": "Достигнут лимит некритичных сообщений в неделю",
    "quiet_hours": "Тихие часы — покажем позже",
    "stale_data": "Данные устарели — сначала обновите остаток",
    "insufficient_data": "Данных недостаточно для уверенного предупреждения",
    "far_horizon": "Риск дальше 14 дней — пока рано беспокоить",
    "mode_quiet": "Тихий режим: только критичные угрозы обязательным платежам",
    "mode_smart_minor": "Умный режим: неопасный для обязательных платежей риск не показываем",
    "type_disabled": "Вы отключили этот тип предупреждений",
    "expected_recurring": "Завтра ожидается знакомый регулярный платёж",
}


def recurring_scope(obligation_id: str) -> str:
    """Стабильный ключ opt-out для одного регулярного события."""
    return f"{EXPECTED_RECURRING}:{obligation_id}"


def reminder_scope(event_key: str) -> str | None:
    """``expected_recurring:<obligation>:<date>`` → ключ отключения события."""
    parts = event_key.split(":")
    if len(parts) != 3 or parts[0] != EXPECTED_RECURRING:
        return None
    return recurring_scope(parts[1])


def ensure_recurring_reminders(
    db: Session, user: User, today: datetime, created_at: datetime | None = None
) -> list[Alert]:
    """Лениво создаёт напоминания за сутки без фонового воркера.

    ``today`` приходит из того же момента, что использует прогноз: для живого учебного
    аккаунта это виртуальное время, для реального пользователя — текущее.
    """
    created_at = created_at or datetime.now(UTC)
    local_day = today.astimezone(ZoneInfo(user.timezone)).date()
    due_day = local_day + timedelta(days=1)
    settings = get_settings(db, user)
    disabled = set(settings.disabled_types or ())
    if EXPECTED_RECURRING in disabled:
        return []

    obligations = db.scalars(
        select(Obligation).where(
            Obligation.user_id == user.id,
            Obligation.status == ObligationStatus.CONFIRMED,
            Obligation.recurrence.in_((Recurrence.WEEKLY, Recurrence.MONTHLY)),
        )
    )
    created: list[Alert] = []
    for obligation in obligations:
        scope = recurring_scope(obligation.id)
        if scope in disabled:
            continue
        due = next(
            occurrences(
                obligation.due_date,
                obligation.recurrence,
                due_day,
                due_day,
                obligation.recurrence_day,
            ),
            None,
        )
        if due is None:
            continue
        event_key = f"{scope}:{due.isoformat()}"
        exists = db.scalar(
            select(Alert.id).where(Alert.user_id == user.id, Alert.event_key == event_key)
        )
        if exists is not None:
            continue
        alert = Alert(
            id=new_id("alr"),
            user_id=user.id,
            forecast_run_id=None,
            event_key=event_key,
            priority=Priority.NORMAL,
            action=AlertAction.SEND,
            reason=EXPECTED_RECURRING,
            risk_date=due,
            shortfall_minor=None,
            delivery_status="in_app",
            message=(
                f"Завтра обычно списывается {rub(obligation.amount_minor)} "
                f"за «{obligation.title}». "
                "Мы уже учли платёж в прогнозе."
            ),
            created_at=created_at,
        )
        db.add(alert)
        created.append(alert)
    db.flush()
    return created


def get_settings(db: Session, user: User) -> NotificationSettings:
    settings = db.get(NotificationSettings, user.id)
    if settings is None:
        settings = NotificationSettings(user_id=user.id)
        db.add(settings)
        db.flush()
    return settings


def message(result: ForecastResult, decision: Decision, data_as_of: datetime) -> str:
    """Один тезис, дата, причина, возможное действие и ограничение модели (11.4)."""
    if result.risk_date is None:
        return ""
    when = day_text(result.risk_date)
    cause = next((d for d in result.drivers if d.kind in ("obligation", "scenario")), None)
    cause_text = (
        f" из-за платежа «{cause.label}» {rub(cause.amount_minor)}" if cause is not None else ""
    )
    limitation = f"Это оценка модели по данным на {day_text(data_as_of.date())}."
    if decision.reason == "stale_data":
        return f"Обновите остаток: по старым данным возможен риск нехватки около {when}."
    if result.risk_level == "high":
        head = (
            f"На {when} возможна нехватка около {rub(result.shortfall_minor)} до резерва"
            f"{cause_text}."
        )
    else:
        head = (
            f"Если доход задержится или траты вырастут, около {when} остаток может опуститься "
            f"ниже резерва{cause_text}."
        )
    return f"{head} Проверьте ожидаемый доход и необязательные траты до этой даты. {limitation}"


def evaluate(
    db: Session,
    user: User,
    forecast_id: str,
    result: ForecastResult,
    data_as_of: datetime,
    stale: bool,
    now: datetime | None = None,
) -> Alert | None:
    """Решение по риску из нового прогноза; записывается в журнал вместе с причиной."""
    now = now or datetime.now(UTC)
    settings = get_settings(db, user)
    history = [
        PastAlert(a.action.value, a.priority.value, a.risk_date, a.shortfall_minor, a.created_at)
        for a in db.scalars(
            select(Alert).where(
                Alert.user_id == user.id,
                Alert.event_key == EVENT_TYPE,
                Alert.created_at >= now - HISTORY_WINDOW,
            )
        )
    ]
    signal = RiskSignal(
        level=result.risk_level,
        risk_date=result.risk_date,
        shortfall_minor=result.shortfall_minor,
        today=result.today,
        critical_payment=any(
            d.kind == "obligation" and result.risk_date and d.day and d.day <= result.risk_date
            for d in result.drivers
        ),
        stale=stale,
        insufficient=result.confidence == "insufficient",
    )
    prefs = Preferences(
        mode=settings.mode.value,
        quiet_start=settings.quiet_hours_start,
        quiet_end=settings.quiet_hours_end,
        max_noncritical_per_week=settings.max_noncritical_per_week,
        disabled_types=tuple(settings.disabled_types or ()),
    )
    local_now = now.astimezone(ZoneInfo(user.timezone)).time()
    decision = decide(signal, prefs, history, now, local_now)
    if decision is None:
        return None
    alert = Alert(
        id=new_id("alr"),
        user_id=user.id,
        forecast_run_id=forecast_id,
        event_key=decision.event_key,
        priority=Priority(decision.priority),
        action=AlertAction(decision.action),
        reason=decision.reason,
        risk_date=result.risk_date,
        shortfall_minor=result.shortfall_minor,
        delivery_status={"send": "in_app", "defer": "deferred", "suppress": "suppressed"}[
            decision.action
        ],
        message=message(result, decision, data_as_of),
        created_at=now,
    )
    db.add(alert)
    db.flush()
    return alert


def to_out(alert: Alert) -> AlertOut:
    return AlertOut(
        id=alert.id,
        action=alert.action,
        priority=alert.priority,
        reason=alert.reason,
        reason_text=REASON_TEXT.get(alert.reason, alert.reason),
        message=alert.message,
        risk_date=alert.risk_date,
        shortfall_minor=alert.shortfall_minor,
        forecast_id=alert.forecast_run_id,
        feedback=alert.feedback,
        created_at=alert.created_at,
    )


def analytics(db: Session, user: User, now: datetime | None = None) -> AlertAnalyticsOut:
    now = now or datetime.now(UTC)
    alerts = list(db.scalars(select(Alert).where(Alert.user_id == user.id)))
    feedback = Counter(a.feedback for a in alerts if a.feedback)
    answered = sum(feedback.values())
    return AlertAnalyticsOut(
        total_decisions=len(alerts),
        by_action=dict(Counter(a.action.value for a in alerts)),
        by_reason=dict(Counter(a.reason for a in alerts)),
        feedback=dict(feedback),
        useful_share=round(feedback["useful"] / answered, 3) if answered else None,
        disable_rate=round(feedback["disable_type"] / answered, 3) if answered else None,
        sent_last_7_days=sum(
            1
            for a in alerts
            if a.action == AlertAction.SEND and now - a.created_at < timedelta(days=7)
        ),
    )
