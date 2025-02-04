"""Add stop_loss and take_profit columns to trades table

Revision ID: 2025012500
Revises: 2025012400
Create Date: 2025-01-25 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2025012500"
down_revision = "2025012400"
branch_labels = None
depends_on = None


def upgrade():
    # Add stop_loss and take_profit columns
    op.add_column(
        "trades",
        sa.Column("stop_loss", sa.Numeric(precision=36, scale=18), nullable=True),
    )
    op.add_column(
        "trades",
        sa.Column("take_profit", sa.Numeric(precision=36, scale=18), nullable=True),
    )

    # Create indices for new columns
    op.create_index("idx_trade_stop_loss", "trades", ["stop_loss"])
    op.create_index("idx_trade_take_profit", "trades", ["take_profit"])


def downgrade():
    # Drop indices first
    op.drop_index("idx_trade_stop_loss", table_name="trades")
    op.drop_index("idx_trade_take_profit", table_name="trades")

    # Drop columns
    op.drop_column("trades", "stop_loss")
    op.drop_column("trades", "take_profit")
