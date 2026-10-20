"""Explicit scoped mock-bank consent."""

import sqlalchemy as sa
from alembic import op

from app.db.types import UTCDateTime

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_consents",
        sa.Column(
            "user_id",
            sa.String(40),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("id", sa.String(40), nullable=False, unique=True),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("expires_at", UTCDateTime(), nullable=False),
        sa.Column("revoked_at", UTCDateTime()),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("source_id", sa.String(40), sa.ForeignKey("data_sources.id")),
    )


def downgrade() -> None:
    op.drop_table("bank_consents")
