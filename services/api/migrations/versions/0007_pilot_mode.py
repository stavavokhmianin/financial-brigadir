"""Pilot access codes and the erasure log."""

import sqlalchemy as sa
from alembic import op

from app.db.types import UTCDateTime

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pilot_access_codes",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("expires_at", UTCDateTime(), nullable=False),
        sa.Column("revoked_at", UTCDateTime()),
        sa.Column("last_used_at", UTCDateTime()),
        sa.Column("user_id", sa.String(40), sa.ForeignKey("users.id", ondelete="CASCADE")),
    )
    op.create_index("ix_pilot_access_codes_user_id", "pilot_access_codes", ["user_id"])
    op.create_table(
        "erasure_log",
        sa.Column("user_id", sa.String(40), primary_key=True),
        sa.Column("erased_at", UTCDateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("erasure_log")
    op.drop_index("ix_pilot_access_codes_user_id", table_name="pilot_access_codes")
    op.drop_table("pilot_access_codes")
