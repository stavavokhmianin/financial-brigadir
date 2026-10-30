"""Личный комментарий к операции, отдельно от банковского описания."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.add_column(sa.Column("user_note", sa.String(length=280)))


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.drop_column("user_note")
