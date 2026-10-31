"""Обычная регистрация пользователя: профиль, email и стойкий хэш пароля."""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("display_name", sa.String(length=40)))
        batch.add_column(sa.Column("email", sa.String(length=254)))
        batch.add_column(sa.Column("password_hash", sa.String(length=255)))
        batch.create_index("ix_users_email", ["email"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_email")
        batch.drop_column("password_hash")
        batch.drop_column("email")
        batch.drop_column("display_name")
