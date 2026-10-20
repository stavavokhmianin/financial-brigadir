"""Схема данных MVP (раздел 8.1 ТЗ).

Соглашения:
* деньги — ``BigInteger`` в копейках (суффикс ``_minor``), никаких float;
* время — ``UTCDateTime``; календарные даты (срок платежа, день прогноза) — ``Date``
  в таймзоне пользователя;
* у каждой пользовательской сущности есть ``user_id``, по нему API проверяет владельца;
* ``Household`` (семья) появится после MVP и в схему этапа 1 не входит.
"""

from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, str_enum
from app.domain.enums import (
    AccountType,
    AlertAction,
    CategorySource,
    DataSourceKind,
    ImportStatus,
    IncomeKind,
    NotificationMode,
    ObligationKind,
    ObligationStatus,
    Plan,
    Priority,
    Recurrence,
    TxStatus,
    TxType,
)

ID = String(40)


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    locale: Mapped[str] = mapped_column(String(16), default="ru-RU")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    plan: Mapped[Plan] = mapped_column(str_enum(Plan, "plan"), default=Plan.FREE)
    # Резерв R_t и допустимый риск alpha (разделы 9.1, 9.4) задаёт пользователь.
    risk_preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    consent_versions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    demo_profile: Mapped[str | None] = mapped_column(String(64))
    demo_seed: Mapped[int | None] = mapped_column(Integer)


class AuthSession(Base):
    """Сессия. Хранится только SHA-256 токена, сам токен знает лишь клиент."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class DataSource(Base):
    """Откуда пришли данные: синтетика, CSV, ручной ввод, мок банка (раздел 7.1)."""

    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[DataSourceKind] = mapped_column(str_enum(DataSourceKind, "source_kind"))
    label: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # Дата актуальности данных источника (FR-04): по ней клиент показывает свежесть.
    data_as_of: Mapped[datetime | None] = mapped_column(UTCDateTime)
    history_from: Mapped[date | None] = mapped_column(Date)
    history_to: Mapped[date | None] = mapped_column(Date)
    is_partial: Mapped[bool] = mapped_column(Boolean, default=False)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("blocked_minor >= 0", name="blocked_non_negative"),
        CheckConstraint(
            "credit_limit_minor IS NULL OR credit_limit_minor >= 0", name="limit_non_negative"
        ),
    )

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"))
    external_id: Mapped[str | None] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    bank_name: Mapped[str | None] = mapped_column(String(120))
    type: Mapped[AccountType] = mapped_column(str_enum(AccountType, "account_type"))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    # Для кредитной карты отрицательное значение — текущий долг.
    available_balance_minor: Mapped[int] = mapped_column(BigInteger)
    credit_limit_minor: Mapped[int | None] = mapped_column(BigInteger)
    blocked_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    # Депозит и иные неликвидные средства не складываются со свободными деньгами (7.3).
    is_liquid: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    source: Mapped[DataSource | None] = relationship()


class ImportBatch(Base):
    """Версия импорта: повторная загрузка того же файла идемпотентна (7.2)."""

    __tablename__ = "import_batches"
    __table_args__ = (UniqueConstraint("user_id", "fingerprint"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    filename: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[ImportStatus] = mapped_column(str_enum(ImportStatus, "import_status"))
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    source: Mapped[DataSource] = relationship()


class Transaction(Base):
    """Нормализованное событие реестра (разделы 7.3, 8.2)."""

    __tablename__ = "transactions"
    __table_args__ = (
        # Повторная доставка из того же источника не удваивает операцию (23.2.6).
        UniqueConstraint("account_id", "source_id", "external_id"),
        Index("ix_transactions_user_occurred", "user_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"))
    import_batch_id: Mapped[str | None] = mapped_column(ForeignKey("import_batches.id"))
    external_id: Mapped[str] = mapped_column(String(80))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    booked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Знак: поступление > 0, списание < 0.
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    type: Mapped[TxType] = mapped_column(str_enum(TxType, "tx_type"))
    status: Mapped[TxStatus] = mapped_column(str_enum(TxStatus, "tx_status"))
    category: Mapped[str | None] = mapped_column(String(64))
    category_source: Mapped[CategorySource] = mapped_column(
        str_enum(CategorySource, "category_source"), default=CategorySource.SOURCE
    )
    description: Mapped[str | None] = mapped_column(String(255))
    # Две стороны перевода между своими счетами связаны общим идентификатором.
    transfer_group_id: Mapped[str | None] = mapped_column(String(40), index=True)
    # Возврат ссылается на исходную покупку (инвариант 23.2.4).
    related_transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Obligation(Base):
    """Будущий обязательный платёж (раздел 7.4)."""

    __tablename__ = "obligations"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="amount_positive"),
        CheckConstraint(
            "amount_min_minor IS NULL OR amount_max_minor IS NULL "
            "OR amount_min_minor <= amount_max_minor",
            name="amount_range",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint(
            "recurrence_day IS NULL OR (recurrence_day >= 1 AND recurrence_day <= 31)",
            name="recurrence_day_range",
        ),
        Index("ix_obligations_user_due", "user_id", "due_date"),
    )

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"))
    kind: Mapped[ObligationKind] = mapped_column(str_enum(ObligationKind, "obligation_kind"))
    title: Mapped[str] = mapped_column(String(120))
    # Сумма списания (положительная). Диапазон — для неточных сумм (ЖКХ, кредитка).
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    amount_min_minor: Mapped[int | None] = mapped_column(BigInteger)
    amount_max_minor: Mapped[int | None] = mapped_column(BigInteger)
    due_date: Mapped[date] = mapped_column(Date)
    recurrence: Mapped[Recurrence] = mapped_column(
        str_enum(Recurrence, "recurrence"), default=Recurrence.NONE
    )
    # Желаемый день месяца; 31 в коротком месяце переносится на последний день.
    recurrence_day: Mapped[int | None] = mapped_column(Integer)
    priority: Mapped[Priority] = mapped_column(
        str_enum(Priority, "priority"), default=Priority.CRITICAL
    )
    status: Mapped[ObligationStatus] = mapped_column(
        str_enum(ObligationStatus, "obligation_status")
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    movable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    source: Mapped[DataSource | None] = relationship()

    @property
    def source_kind(self) -> str:
        return self.source.kind.value if self.source is not None else DataSourceKind.MANUAL.value


class IncomeEvent(Base):
    """Ожидаемое поступление с диапазоном даты и суммы (раздел 8.1, US-05)."""

    __tablename__ = "income_events"
    __table_args__ = (
        CheckConstraint("date_from <= date_to", name="date_range"),
        CheckConstraint(
            "amount_min_minor > 0 AND amount_min_minor <= amount_max_minor", name="amount_range"
        ),
        CheckConstraint("probability >= 0 AND probability <= 1", name="probability_range"),
    )

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"))
    kind: Mapped[IncomeKind] = mapped_column(str_enum(IncomeKind, "income_kind"))
    title: Mapped[str] = mapped_column(String(120))
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    amount_min_minor: Mapped[int] = mapped_column(BigInteger)
    amount_max_minor: Mapped[int] = mapped_column(BigInteger)
    probability: Mapped[float] = mapped_column(Float, default=1.0)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence: Mapped[Recurrence] = mapped_column(
        str_enum(Recurrence, "recurrence"), default=Recurrence.NONE
    )
    # Пользователь отметил, что поступления не будет; запись остаётся для истории.
    canceled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    source: Mapped[DataSource | None] = relationship()

    @property
    def source_kind(self) -> str:
        return self.source.kind.value if self.source is not None else DataSourceKind.MANUAL.value


class ForecastRun(Base):
    """Расчёт прогноза со снимком входа и версией модели (разделы 7.9, 13.3)."""

    __tablename__ = "forecast_runs"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key"),
        CheckConstraint("horizon_days >= 1 AND horizon_days <= 365", name="horizon_range"),
    )

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    as_of: Mapped[datetime] = mapped_column(UTCDateTime)
    horizon_days: Mapped[int] = mapped_column(Integer)
    reserve_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    model_version: Mapped[str] = mapped_column(String(40))
    seed: Mapped[int | None] = mapped_column(Integer)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    quality_flags: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Применённый сценарий (покупка, сдвиг дохода) и итог расчёта для GET /forecasts/{id}.
    scenario: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    points: Mapped[list["ForecastPoint"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="ForecastPoint.day"
    )


class ForecastPoint(Base):
    __tablename__ = "forecast_points"
    __table_args__ = (
        UniqueConstraint("run_id", "day"),
        CheckConstraint(
            "risk_probability IS NULL OR (risk_probability >= 0 AND risk_probability <= 1)",
            name="risk_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("forecast_runs.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    p10_minor: Mapped[int] = mapped_column(BigInteger)
    p50_minor: Mapped[int] = mapped_column(BigInteger)
    p90_minor: Mapped[int] = mapped_column(BigInteger)
    risk_probability: Mapped[float | None] = mapped_column(Float)

    run: Mapped[ForecastRun] = relationship(back_populates="points")


class Scenario(Base):
    """What-if: базовый расчёт + дельта-события; история операций не меняется (7.6)."""

    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    base_run_id: Mapped[str] = mapped_column(ForeignKey("forecast_runs.id", ondelete="CASCADE"))
    delta_events: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    result_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Alert(Base):
    """Решение по уведомлению; журналируется без исходной выписки (23.4)."""

    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_user_event", "user_id", "event_key"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    forecast_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="SET NULL")
    )
    event_key: Mapped[str] = mapped_column(String(120))
    priority: Mapped[Priority] = mapped_column(str_enum(Priority, "priority"))
    action: Mapped[AlertAction] = mapped_column(str_enum(AlertAction, "alert_action"))
    reason: Mapped[str] = mapped_column(String(255))
    risk_date: Mapped[date | None] = mapped_column(Date)
    shortfall_minor: Mapped[int | None] = mapped_column(BigInteger)
    delivery_status: Mapped[str] = mapped_column(String(32), default="pending")
    feedback: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class NotificationSettings(Base):
    __tablename__ = "notification_settings"
    __table_args__ = (
        CheckConstraint(
            "max_noncritical_per_week >= 0 AND max_noncritical_per_week <= 14",
            name="weekly_limit_range",
        ),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    mode: Mapped[NotificationMode] = mapped_column(
        str_enum(NotificationMode, "notification_mode"), default=NotificationMode.SMART
    )
    quiet_hours_start: Mapped[time | None] = mapped_column(Time)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time)
    max_noncritical_per_week: Mapped[int] = mapped_column(Integer, default=2)
    disabled_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class AuditEvent(Base):
    """Журнал действий без финансовых подробностей (разделы 7.9, 25)."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(64))
    object_type: Mapped[str | None] = mapped_column(String(40))
    object_id: Mapped[str | None] = mapped_column(String(40))
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
