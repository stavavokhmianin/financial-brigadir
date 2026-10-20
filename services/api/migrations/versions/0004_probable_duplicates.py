"""probable duplicates

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-21 00:50:51.804567
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("review_reason", sa.String(length=40), nullable=True))
        batch_op.add_column(
            sa.Column("duplicate_candidate_id", sa.String(length=40), nullable=True)
        )
        batch_op.add_column(sa.Column("duplicate_of_id", sa.String(length=40), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_transactions_duplicate_candidate_id_transactions"),
            "transactions",
            ["duplicate_candidate_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_transactions_duplicate_of_id_transactions"),
            "transactions",
            ["duplicate_of_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_transactions_duplicate_of_id_transactions"), type_="foreignkey"
        )
        batch_op.drop_constraint(
            batch_op.f("fk_transactions_duplicate_candidate_id_transactions"), type_="foreignkey"
        )
        batch_op.drop_column("duplicate_of_id")
        batch_op.drop_column("duplicate_candidate_id")
        batch_op.drop_column("review_reason")
