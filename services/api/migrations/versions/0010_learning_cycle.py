"""Метки операций и живой учебный аккаунт (ADR-0007)."""

import sqlalchemy as sa
from alembic import op

from app.db.types import UTCDateTime

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

LABELS = ("mandatory", "regular", "reducible", "one_off")


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.add_column(
            sa.Column(
                "label",
                sa.Enum(
                    *LABELS, name="tx_label", native_enum=False, create_constraint=False, length=32
                ),
            )
        )
        batch.add_column(sa.Column("labeled_at", UTCDateTime()))
    op.create_table(
        "live_clocks",
        sa.Column(
            "user_id",
            sa.String(length=40),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("virtual_start", UTCDateTime(), nullable=False),
        sa.Column("virtual_end", UTCDateTime(), nullable=False),
        sa.Column("real_start", UTCDateTime(), nullable=False),
        sa.Column("seconds_per_day", sa.Integer(), nullable=False),
        sa.Column("paused_at", UTCDateTime()),
        sa.Column("paused_seconds", sa.Float(), nullable=False),
        sa.Column("skipped_days", sa.Integer(), nullable=False),
        sa.Column("revealed_until", UTCDateTime(), nullable=False),
        sa.Column("revealed_total", sa.Integer(), nullable=False),
    )
    op.create_table(
        "live_pending_transactions",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=40),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("occurred_at", UTCDateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("counts_in_balance", sa.Boolean(), nullable=False),
    )
    op.create_index(
        "ix_live_pending_user_occurred", "live_pending_transactions", ["user_id", "occurred_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_live_pending_user_occurred", table_name="live_pending_transactions")
    op.drop_table("live_pending_transactions")
    op.drop_table("live_clocks")
    with op.batch_alter_table("transactions") as batch:
        batch.drop_column("labeled_at")
        batch.drop_column("label")
