"""Отдельное состояние прочтения для счётчика колокольчика."""

import sqlalchemy as sa
from alembic import op

from app.db.types import UTCDateTime

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("alerts") as batch:
        batch.add_column(sa.Column("read_at", UTCDateTime()))


def downgrade() -> None:
    with op.batch_alter_table("alerts") as batch:
        batch.drop_column("read_at")
