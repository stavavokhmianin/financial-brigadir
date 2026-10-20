"""Export and erase only the authenticated profile, including derived data."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    Alert,
    AuditEvent,
    AuthSession,
    BankConsent,
    DataSource,
    ForecastPoint,
    ForecastRun,
    ImportBatch,
    IncomeEvent,
    NotificationSettings,
    Obligation,
    Scenario,
    Transaction,
    User,
)

EXPORT_MODELS = (
    BankConsent,
    Account,
    DataSource,
    Transaction,
    ImportBatch,
    Obligation,
    IncomeEvent,
    ForecastRun,
    Scenario,
    Alert,
    NotificationSettings,
    AuditEvent,
)


def export_profile(db: Session, user: User) -> dict[str, Any]:
    def row(item: Any) -> dict[str, Any]:
        return {column.name: getattr(item, column.name) for column in item.__table__.columns}

    result: dict[str, Any] = {
        "schema_version": "1.0",
        "exported_at": datetime.now(UTC),
        "user": row(user),
    }
    for model in EXPORT_MODELS:
        result[model.__tablename__] = [
            row(item) for item in db.scalars(select(model).where(model.user_id == user.id))
        ]
    result["forecast_points"] = [
        row(item)
        for item in db.scalars(
            select(ForecastPoint).join(ForecastRun).where(ForecastRun.user_id == user.id)
        )
    ]
    # Auth sessions and their hashes are intentionally never exported.
    db.add(AuditEvent(user_id=user.id, action="profile_exported"))
    db.commit()
    return result


def erase_profile(db: Session, user: User) -> None:
    # Explicit dependency order also works with SQLite FK enforcement enabled.
    db.execute(
        delete(ForecastPoint).where(
            ForecastPoint.run_id.in_(select(ForecastRun.id).where(ForecastRun.user_id == user.id))
        )
    )
    for model in (
        Scenario,
        Alert,
        ForecastRun,
        Transaction,
        Obligation,
        IncomeEvent,
        Account,
        ImportBatch,
        BankConsent,
        DataSource,
        NotificationSettings,
        AuditEvent,
        AuthSession,
    ):
        db.execute(delete(model).where(model.user_id == user.id))
    db.execute(delete(User).where(User.id == user.id))
    db.commit()


def purge_expired_profiles(db: Session, now: datetime | None = None) -> int:
    """Delete up to 100 abandoned demo profiles per worker tick after seven days."""
    now = now or datetime.now(UTC)
    active = select(AuthSession.user_id).where(
        AuthSession.expires_at > now, AuthSession.revoked_at.is_(None)
    )
    users = list(
        db.scalars(
            select(User)
            .where(
                User.is_demo.is_(True),
                User.created_at < now - timedelta(days=7),
                User.id.not_in(active),
            )
            .limit(100)
        )
    )
    for user in users:
        erase_profile(db, user)
    return len(users)
