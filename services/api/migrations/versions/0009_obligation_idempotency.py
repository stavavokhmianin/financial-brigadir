"""Idempotency keys for manually created obligations."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("obligations") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(length=80)))
        batch.create_unique_constraint(
            "uq_obligations_user_idempotency_key", ["user_id", "idempotency_key"]
        )


def downgrade() -> None:
    with op.batch_alter_table("obligations") as batch:
        batch.drop_constraint("uq_obligations_user_idempotency_key", type_="unique")
        batch.drop_column("idempotency_key")
