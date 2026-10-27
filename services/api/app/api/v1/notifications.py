from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.core.errors import APIError, error_responses
from app.db.models import AuditEvent, NotificationSettings
from app.modules.alerts import get_settings
from app.schemas.alerts import NotificationSettingsOut, NotificationSettingsPatch

router = APIRouter(prefix="/notification-settings", tags=["alerts"])


@router.get(
    "",
    operation_id="getNotificationSettings",
    summary="Текущие настройки уведомлений",
    responses=error_responses(401),
)
def read_settings(user: CurrentUser, db: DbSession) -> NotificationSettingsOut:
    settings = get_settings(db, user)
    db.commit()
    return NotificationSettingsOut.model_validate(settings)


@router.patch(
    "",
    operation_id="updateNotificationSettings",
    summary="Режим уведомлений, тихие часы и лимит некритичных сообщений",
    responses=error_responses(400, 401),
)
def update_settings(
    body: NotificationSettingsPatch, user: CurrentUser, db: DbSession
) -> NotificationSettingsOut:
    settings = db.get(NotificationSettings, user.id)
    if settings is None:
        settings = NotificationSettings(user_id=user.id)
        db.add(settings)
    changes = body.model_dump(exclude_unset=True)
    start = changes.get("quiet_hours_start", settings.quiet_hours_start)
    end = changes.get("quiet_hours_end", settings.quiet_hours_end)
    if (start is None) != (end is None):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            "bad_quiet_hours",
            "Тихие часы задаются парой quiet_hours_start/quiet_hours_end",
        )
    for field, value in changes.items():
        if value is None and field in ("mode", "max_noncritical_per_week", "disabled_types"):
            continue
        setattr(settings, field, value)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="notification_settings_updated",
            object_type="notification_settings",
            meta={"fields": sorted(changes)},
        )
    )
    db.commit()
    db.refresh(settings)
    return NotificationSettingsOut.model_validate(settings)
