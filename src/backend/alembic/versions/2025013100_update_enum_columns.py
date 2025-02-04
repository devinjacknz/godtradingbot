"""Update enum columns to use integer values."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2025013100"
down_revision = "2025012200"
branch_labels = None
depends_on = None


def upgrade():
    """Upgrade database schema."""
    # Convert strategy_type to integer
    op.execute(
        """
        ALTER TABLE strategies 
        ALTER COLUMN strategy_type TYPE integer 
        USING (
            CASE COALESCE(strategy_type::text, 'momentum')
                WHEN 'momentum' THEN 1
                WHEN 'mean_reversion' THEN 2
                WHEN 'breakout' THEN 3
                WHEN 'trend_following' THEN 4
                WHEN 'early_entry' THEN 5
                WHEN 'batch_position' THEN 6
                WHEN 'capital_rotation' THEN 7
                WHEN 'social_sentiment' THEN 8
                WHEN 'technical_analysis' THEN 9
                WHEN 'automated_trading' THEN 10
                WHEN 'copy_trading' THEN 11
                WHEN 'market_making' THEN 12
                WHEN 'multi_token_monitoring' THEN 13
                WHEN 'stop_loss_take_profit' THEN 14
                ELSE 1  -- Default to momentum
            END
        )"""
    )

    # Convert trade status to integer
    op.execute(
        """
        ALTER TABLE trades 
        ALTER COLUMN status TYPE integer 
        USING (
            CASE COALESCE(status::text, 'pending')
                WHEN 'pending' THEN 1
                WHEN 'open' THEN 2
                WHEN 'closed' THEN 3
                WHEN 'cancelled' THEN 4
                WHEN 'failed' THEN 5
                ELSE 1  -- Default to pending
            END
        )
    """
    )


def downgrade():
    """Downgrade database schema."""
    # Convert strategy_type back to enum
    op.execute(
        """
        ALTER TABLE strategies 
        ALTER COLUMN strategy_type TYPE text 
        USING (
            CASE strategy_type
                WHEN 1 THEN 'momentum'
                WHEN 2 THEN 'mean_reversion'
                WHEN 3 THEN 'breakout'
                WHEN 4 THEN 'trend_following'
                WHEN 5 THEN 'early_entry'
                WHEN 6 THEN 'batch_position'
                WHEN 7 THEN 'capital_rotation'
                WHEN 8 THEN 'social_sentiment'
                WHEN 9 THEN 'technical_analysis'
                WHEN 10 THEN 'automated_trading'
                WHEN 11 THEN 'copy_trading'
                WHEN 12 THEN 'market_making'
                WHEN 13 THEN 'multi_token_monitoring'
                WHEN 14 THEN 'stop_loss_take_profit'
            END::text
        )
    """
    )

    # Convert trade status back to enum
    op.execute(
        """
        ALTER TABLE trades 
        ALTER COLUMN status TYPE text 
        USING (
            CASE status
                WHEN 1 THEN 'pending'
                WHEN 2 THEN 'open'
                WHEN 3 THEN 'closed'
                WHEN 4 THEN 'cancelled'
                WHEN 5 THEN 'failed'
            END::text
        )
    """
    )
