"""Add fee column to trades table

Revision ID: 2025012600
Revises: 2025012500
Create Date: 2025-01-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2025012600"
down_revision = "2025012500"
branch_labels = None
depends_on = None


def upgrade():
    # Add fee column
    op.add_column(
        "trades", sa.Column("fee", sa.Numeric(precision=36, scale=18), nullable=True)
    )

    # Create index for fee column
    op.create_index("idx_trade_fee", "trades", ["fee"])


def downgrade():
    # Drop index first
    op.drop_index("idx_trade_fee", table_name="trades")

    # Drop column
    op.drop_column("trades", "fee")
