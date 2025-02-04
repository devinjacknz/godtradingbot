"""Add market data and cache models

Revision ID: 20240128_market_data
Revises: initial_migration
Create Date: 2024-01-28 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "20240128_market_data"
down_revision = "initial_migration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create market_metrics table
    op.create_table(
        "market_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("volatility", sa.Float(), nullable=False),
        sa.Column("volume_profile", JSONB(), nullable=False),
        sa.Column("liquidity_score", sa.Float(), nullable=False),
        sa.Column("momentum_indicators", JSONB(), nullable=False),
        sa.Column("technical_indicators", JSONB(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_metrics_symbol", "market_metrics", ["symbol"])
    op.create_index("ix_market_metrics_timestamp", "market_metrics", ["timestamp"])

    # Create trading_signals table
    op.create_table(
        "trading_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.Column("timeframe", sa.String(), nullable=False),
        sa.Column("indicators_used", JSONB(), nullable=False),
        sa.Column("analysis_data", JSONB(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trading_signals_symbol", "trading_signals", ["symbol"])
    op.create_index("ix_trading_signals_timestamp", "trading_signals", ["timestamp"])


def downgrade() -> None:
    op.drop_table("trading_signals")
    op.drop_table("market_metrics")
