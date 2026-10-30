from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.errors import APIError, error_responses, not_found
from app.db.models import Alert, AuditEvent
from app.domain.enums import AlertAction
from app.modules.alert_policy import EVENT_TYPE
from app.modules.alerts import (
    EXPECTED_RECURRING,
    analytics,
    ensure_recurring_reminders,
    get_settings,
    reminder_scope,
    to_out,
)
from app.modules.forecasting import current_as_of
from app.schemas.alerts import AlertAnalyticsOut, AlertFeedback, AlertOut, AlertsOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get(
    "",
    operation_id="listAlerts",
    summary="Предупреждения и причины подавления (7.7): send, defer, suppress",
    responses=error_responses(401),
)
def list_alerts(
    user: CurrentUser,
    db: DbSession,
    action: AlertAction | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AlertsOut:
    ensure_recurring_reminders(db, user, current_as_of(db, user))
    db.commit()
    query = select(Alert).where(Alert.user_id == user.id)
    if action is not None:
        query = query.where(Alert.action == action)
    rows = db.scalars(query.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit))
    return AlertsOut(items=[to_out(a) for a in rows])


@router.get(
    "/analytics",
    operation_id="getAlertAnalytics",
    summary="Метрики уведомлений: нагрузка, причины подавления, полезность, отключения",
    responses=error_responses(401),
)
def get_analytics(user: CurrentUser, db: DbSession) -> AlertAnalyticsOut:
    return analytics(db, user)


@router.patch(
    "/{alert_id}",
    operation_id="sendAlertFeedback",
    summary="Отзыв о предупреждении: полезно, не актуально или отключить этот тип (23.4)",
    responses=error_responses(401, 404),
)
def send_feedback(alert_id: str, body: AlertFeedback, user: CurrentUser, db: DbSession) -> AlertOut:
    alert = db.scalar(select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id))
    if alert is None:
        raise not_found("Предупреждение")
    alert.feedback = body.feedback
    if body.feedback == "disable_event":
        scope = reminder_scope(alert.event_key)
        if scope is None:
            raise APIError(
                status.HTTP_400_BAD_REQUEST,
                "not_event_notification",
                "Точечное отключение доступно только для регулярного события",
            )
        settings = get_settings(db, user)
        disabled = set(settings.disabled_types or ())
        disabled.add(scope)
        settings.disabled_types = sorted(disabled)
    elif body.feedback == "disable_type":
        settings = get_settings(db, user)
        disabled = set(settings.disabled_types or ())
        disabled.add(
            EXPECTED_RECURRING
            if alert.event_key.startswith(f"{EXPECTED_RECURRING}:")
            else EVENT_TYPE
        )
        settings.disabled_types = sorted(disabled)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="alert_feedback",
            object_type="alert",
            object_id=alert.id,
            meta={"feedback": body.feedback},
        )
    )
    db.commit()
    db.refresh(alert)
    return to_out(alert)
