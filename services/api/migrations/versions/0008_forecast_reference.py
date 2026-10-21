"""Reference model paths stored with each base forecast."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("forecast_runs", sa.Column("reference", sa.JSON()))


def downgrade() -> None:
    op.drop_column("forecast_runs", "reference")
