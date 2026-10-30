"""Поиск повторений: получатель у обязательства и решения по кандидатам (ADR-0007, этап B)."""

import sqlalchemy as sa
from alembic import op

from app.db.types import UTCDateTime

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("obligations") as batch:
        batch.add_column(sa.Column("match_key", sa.String(length=120)))
    op.create_table(
        "recurring_decisions",
        sa.Column(
            "user_id",
            sa.String(length=40),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("key", sa.String(length=40), primary_key=True),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column(
            "obligation_id",
            sa.String(length=40),
            sa.ForeignKey("obligations.id", ondelete="SET NULL"),
        ),
        sa.Column("decided_at", UTCDateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("recurring_decisions")
    with op.batch_alter_table("obligations") as batch:
        batch.drop_column("match_key")
