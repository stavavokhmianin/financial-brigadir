"""Export and erase only the authenticated profile, including derived data."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
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
    ErasureRecord,
    ForecastPoint,
    ForecastRun,
    ImportBatch,
    IncomeEvent,
    LiveClock,
    LivePendingTransaction,
    NotificationSettings,
    Obligation,
    PilotAccessCode,
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
    LiveClock,
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


def erase_profile(db: Session, user: User, log_path: str | None = None) -> None:
    # Explicit dependency order also works with SQLite FK enforcement enabled.
    db.execute(
        delete(ForecastPoint).where(
            ForecastPoint.run_id.in_(select(ForecastRun.id).where(ForecastRun.user_id == user.id))
        )
    )
    for model in (
        LivePendingTransaction,
        LiveClock,
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
        PilotAccessCode,
    ):
        db.execute(delete(model).where(model.user_id == user.id))
    db.execute(delete(User).where(User.id == user.id))
    db.merge(ErasureRecord(user_id=user.id, erased_at=datetime.now(UTC)))
    db.commit()
    if log_path:
        # Файл живёт вне БД и вне бэкапа: восстановленная копия не «забудет» удаление.
        with Path(log_path).open("a", encoding="utf-8") as log:
            log.write(user.id + "\n")


def reapply_erasures(db: Session, log_path: str | None = None) -> int:
    """После восстановления бэкапа удаляет профили, стёртые после его создания."""
    erased = set(db.scalars(select(ErasureRecord.user_id)))
    if log_path and Path(log_path).exists():
        erased |= {
            line.strip()
            for line in Path(log_path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    users = list(db.scalars(select(User).where(User.id.in_(erased)))) if erased else []
    for user in users:
        erase_profile(db, user)
    # Восстановленный журнал в БД мог отстать от файла — дополняем его.
    for user_id in erased:
        db.merge(ErasureRecord(user_id=user_id))
    db.commit()
    return len(users)


def purge_expired_profiles(
    db: Session, now: datetime | None = None, log_path: str | None = None
) -> int:
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
        erase_profile(db, user, log_path)
    return len(users)
