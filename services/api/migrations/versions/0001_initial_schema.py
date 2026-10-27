"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-19 19:03:06.506214
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column(
            "plan",
            sa.Enum(
                "free", "plus", name="plan", native_enum=False, create_constraint=False, length=32
            ),
            nullable=False,
        ),
        sa.Column("risk_preferences", sa.JSON(), nullable=False),
        sa.Column("consent_versions", sa.JSON(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("demo_profile", sa.String(length=64), nullable=True),
        sa.Column("demo_seed", sa.Integer(), nullable=True),
        sa.CheckConstraint("\"plan\" IN ('free', 'plus')", name=op.f("ck_users_plan")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("object_type", sa.String(length=40), nullable=True),
        sa.Column("object_id", sa.String(length=40), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_audit_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    with op.batch_alter_table("audit_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_audit_events_user_id"), ["user_id"], unique=False)

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_sessions_token_hash")),
    )
    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_auth_sessions_user_id"), ["user_id"], unique=False)

    op.create_table(
        "data_sources",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "synthetic",
                "csv",
                "manual",
                "bank_mock",
                name="source_kind",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("history_from", sa.Date(), nullable=True),
        sa.Column("history_to", sa.Date(), nullable=True),
        sa.Column("is_partial", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('synthetic', 'csv', 'manual', 'bank_mock')",
            name=op.f("ck_data_sources_source_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_data_sources_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_sources")),
    )
    with op.batch_alter_table("data_sources", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_data_sources_user_id"), ["user_id"], unique=False)

    op.create_table(
        "forecast_runs",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("reserve_minor", sa.BigInteger(), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("quality_flags", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "horizon_days >= 1 AND horizon_days <= 365", name=op.f("ck_forecast_runs_horizon_range")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_forecast_runs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast_runs")),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name=op.f("uq_forecast_runs_user_id_idempotency_key")
        ),
    )
    with op.batch_alter_table("forecast_runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_forecast_runs_user_id"), ["user_id"], unique=False)

    op.create_table(
        "notification_settings",
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column(
            "mode",
            sa.Enum(
                "quiet",
                "smart",
                "active",
                name="notification_mode",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("quiet_hours_start", sa.Time(), nullable=True),
        sa.Column("quiet_hours_end", sa.Time(), nullable=True),
        sa.Column("max_noncritical_per_week", sa.Integer(), nullable=False),
        sa.Column("disabled_types", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "mode IN ('quiet', 'smart', 'active')",
            name=op.f("ck_notification_settings_notification_mode"),
        ),
        sa.CheckConstraint(
            "max_noncritical_per_week >= 0 AND max_noncritical_per_week <= 14",
            name=op.f("ck_notification_settings_weekly_limit_range"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_settings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_notification_settings")),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=40), nullable=True),
        sa.Column("external_id", sa.String(length=80), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("bank_name", sa.String(length=120), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "debit",
                "credit_card",
                "savings",
                "deposit",
                "cash",
                name="account_type",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("available_balance_minor", sa.BigInteger(), nullable=False),
        sa.Column("credit_limit_minor", sa.BigInteger(), nullable=True),
        sa.Column("blocked_minor", sa.BigInteger(), nullable=False),
        sa.Column("is_liquid", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "type IN ('debit', 'credit_card', 'savings', 'deposit', 'cash')",
            name=op.f("ck_accounts_account_type"),
        ),
        sa.CheckConstraint("blocked_minor >= 0", name=op.f("ck_accounts_blocked_non_negative")),
        sa.CheckConstraint(
            "credit_limit_minor IS NULL OR credit_limit_minor >= 0",
            name=op.f("ck_accounts_limit_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["data_sources.id"], name=op.f("fk_accounts_source_id_data_sources")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_accounts_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
    )
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_accounts_user_id"), ["user_id"], unique=False)

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("forecast_run_id", sa.String(length=40), nullable=True),
        sa.Column("event_key", sa.String(length=120), nullable=False),
        sa.Column(
            "priority",
            sa.Enum(
                "critical",
                "normal",
                name="priority",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.Enum(
                "send",
                "defer",
                "suppress",
                name="alert_action",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("risk_date", sa.Date(), nullable=True),
        sa.Column("shortfall_minor", sa.BigInteger(), nullable=True),
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        sa.Column("feedback", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('send', 'defer', 'suppress')", name=op.f("ck_alerts_alert_action")
        ),
        sa.CheckConstraint("priority IN ('critical', 'normal')", name=op.f("ck_alerts_priority")),
        sa.ForeignKeyConstraint(
            ["forecast_run_id"],
            ["forecast_runs.id"],
            name=op.f("fk_alerts_forecast_run_id_forecast_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_alerts_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.create_index("ix_alerts_user_event", ["user_id", "event_key"], unique=False)

    op.create_table(
        "forecast_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("p10_minor", sa.BigInteger(), nullable=False),
        sa.Column("p50_minor", sa.BigInteger(), nullable=False),
        sa.Column("p90_minor", sa.BigInteger(), nullable=False),
        sa.Column("risk_probability", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "risk_probability IS NULL OR (risk_probability >= 0 AND risk_probability <= 1)",
            name=op.f("ck_forecast_points_risk_range"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["forecast_runs.id"],
            name=op.f("fk_forecast_points_run_id_forecast_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast_points")),
        sa.UniqueConstraint("run_id", "day", name=op.f("uq_forecast_points_run_id_day")),
    )
    op.create_table(
        "import_batches",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=40), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "preview",
                "imported",
                "rejected",
                name="import_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("rows_total", sa.Integer(), nullable=False),
        sa.Column("rows_imported", sa.Integer(), nullable=False),
        sa.Column("rows_duplicate", sa.Integer(), nullable=False),
        sa.Column("rows_rejected", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('preview', 'imported', 'rejected')",
            name=op.f("ck_import_batches_import_status"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["data_sources.id"],
            name=op.f("fk_import_batches_source_id_data_sources"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_import_batches_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batches")),
        sa.UniqueConstraint(
            "user_id", "fingerprint", name=op.f("uq_import_batches_user_id_fingerprint")
        ),
    )
    with op.batch_alter_table("import_batches", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_import_batches_user_id"), ["user_id"], unique=False)

    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("base_run_id", sa.String(length=40), nullable=False),
        sa.Column("delta_events", sa.JSON(), nullable=False),
        sa.Column("result_run_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["base_run_id"],
            ["forecast_runs.id"],
            name=op.f("fk_scenarios_base_run_id_forecast_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["result_run_id"],
            ["forecast_runs.id"],
            name=op.f("fk_scenarios_result_run_id_forecast_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_scenarios_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenarios")),
    )
    with op.batch_alter_table("scenarios", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_scenarios_user_id"), ["user_id"], unique=False)

    op.create_table(
        "income_events",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.String(length=40), nullable=True),
        sa.Column("source_id", sa.String(length=40), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "salary",
                "advance",
                "freelance",
                "other",
                name="income_kind",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("amount_min_minor", sa.BigInteger(), nullable=False),
        sa.Column("amount_max_minor", sa.BigInteger(), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column(
            "recurrence",
            sa.Enum(
                "none",
                "weekly",
                "monthly",
                name="recurrence",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('salary', 'advance', 'freelance', 'other')",
            name=op.f("ck_income_events_income_kind"),
        ),
        sa.CheckConstraint(
            "recurrence IN ('none', 'weekly', 'monthly')", name=op.f("ck_income_events_recurrence")
        ),
        sa.CheckConstraint(
            "amount_min_minor > 0 AND amount_min_minor <= amount_max_minor",
            name=op.f("ck_income_events_amount_range"),
        ),
        sa.CheckConstraint("date_from <= date_to", name=op.f("ck_income_events_date_range")),
        sa.CheckConstraint(
            "probability >= 0 AND probability <= 1", name=op.f("ck_income_events_probability_range")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_income_events_account_id_accounts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["data_sources.id"], name=op.f("fk_income_events_source_id_data_sources")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_income_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_income_events")),
    )
    with op.batch_alter_table("income_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_income_events_user_id"), ["user_id"], unique=False)

    op.create_table(
        "obligations",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.String(length=40), nullable=True),
        sa.Column("source_id", sa.String(length=40), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "rent",
                "loan",
                "credit_card",
                "utilities",
                "subscription",
                "installment",
                "manual",
                name="obligation_kind",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("amount_min_minor", sa.BigInteger(), nullable=True),
        sa.Column("amount_max_minor", sa.BigInteger(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column(
            "recurrence",
            sa.Enum(
                "none",
                "weekly",
                "monthly",
                name="recurrence",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("recurrence_day", sa.Integer(), nullable=True),
        sa.Column(
            "priority",
            sa.Enum(
                "critical",
                "normal",
                name="priority",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "confirmed",
                "inferred",
                "uncertain",
                "canceled",
                name="obligation_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("movable", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('rent', 'loan', 'credit_card', 'utilities', 'subscription', 'installment', 'manual')",
            name=op.f("ck_obligations_obligation_kind"),
        ),
        sa.CheckConstraint(
            "priority IN ('critical', 'normal')", name=op.f("ck_obligations_priority")
        ),
        sa.CheckConstraint(
            "recurrence IN ('none', 'weekly', 'monthly')", name=op.f("ck_obligations_recurrence")
        ),
        sa.CheckConstraint(
            "status IN ('confirmed', 'inferred', 'uncertain', 'canceled')",
            name=op.f("ck_obligations_obligation_status"),
        ),
        sa.CheckConstraint(
            "amount_min_minor IS NULL OR amount_max_minor IS NULL OR amount_min_minor <= amount_max_minor",
            name=op.f("ck_obligations_amount_range"),
        ),
        sa.CheckConstraint("amount_minor > 0", name=op.f("ck_obligations_amount_positive")),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_obligations_confidence_range")
        ),
        sa.CheckConstraint(
            "recurrence_day IS NULL OR (recurrence_day >= 1 AND recurrence_day <= 31)",
            name=op.f("ck_obligations_recurrence_day_range"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_obligations_account_id_accounts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["data_sources.id"], name=op.f("fk_obligations_source_id_data_sources")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_obligations_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_obligations")),
    )
    with op.batch_alter_table("obligations", schema=None) as batch_op:
        batch_op.create_index("ix_obligations_user_due", ["user_id", "due_date"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=40), nullable=False),
        sa.Column("import_batch_id", sa.String(length=40), nullable=True),
        sa.Column("external_id", sa.String(length=80), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "income",
                "expense",
                "transfer_in",
                "transfer_out",
                "refund",
                "credit_purchase",
                "credit_payment",
                "fee",
                name="tx_type",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "posted",
                "pending",
                "canceled",
                name="tx_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column(
            "category_source",
            sa.Enum(
                "source",
                "rule",
                "manual",
                name="category_source",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("transfer_group_id", sa.String(length=40), nullable=True),
        sa.Column("related_transaction_id", sa.String(length=40), nullable=True),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category_source IN ('source', 'rule', 'manual')",
            name=op.f("ck_transactions_category_source"),
        ),
        sa.CheckConstraint(
            "status IN ('posted', 'pending', 'canceled')", name=op.f("ck_transactions_tx_status")
        ),
        sa.CheckConstraint(
            "type IN ('income', 'expense', 'transfer_in', 'transfer_out', 'refund', 'credit_purchase', 'credit_payment', 'fee')",
            name=op.f("ck_transactions_tx_type"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_transactions_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batches.id"],
            name=op.f("fk_transactions_import_batch_id_import_batches"),
        ),
        sa.ForeignKeyConstraint(
            ["related_transaction_id"],
            ["transactions.id"],
            name=op.f("fk_transactions_related_transaction_id_transactions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["data_sources.id"], name=op.f("fk_transactions_source_id_data_sources")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_transactions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
        sa.UniqueConstraint(
            "account_id",
            "source_id",
            "external_id",
            name=op.f("uq_transactions_account_id_source_id_external_id"),
        ),
    )
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_transactions_transfer_group_id"), ["transfer_group_id"], unique=False
        )
        batch_op.create_index(
            "ix_transactions_user_occurred", ["user_id", "occurred_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.drop_index("ix_transactions_user_occurred")
        batch_op.drop_index(batch_op.f("ix_transactions_transfer_group_id"))

    op.drop_table("transactions")
    with op.batch_alter_table("obligations", schema=None) as batch_op:
        batch_op.drop_index("ix_obligations_user_due")

    op.drop_table("obligations")
    with op.batch_alter_table("income_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_income_events_user_id"))

    op.drop_table("income_events")
    with op.batch_alter_table("scenarios", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_scenarios_user_id"))

    op.drop_table("scenarios")
    with op.batch_alter_table("import_batches", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_import_batches_user_id"))

    op.drop_table("import_batches")
    op.drop_table("forecast_points")
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.drop_index("ix_alerts_user_event")

    op.drop_table("alerts")
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_accounts_user_id"))

    op.drop_table("accounts")
    op.drop_table("notification_settings")
    with op.batch_alter_table("forecast_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_forecast_runs_user_id"))

    op.drop_table("forecast_runs")
    with op.batch_alter_table("data_sources", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_data_sources_user_id"))

    op.drop_table("data_sources")
    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_auth_sessions_user_id"))

    op.drop_table("auth_sessions")
    with op.batch_alter_table("audit_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_audit_events_user_id"))

    op.drop_table("audit_events")
    op.drop_table("users")
