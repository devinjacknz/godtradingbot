"""rename_parameters_to_config

Revision ID: 9de9048d3cce
Revises: 2025012700
Create Date: 2025-01-22 06:58:55.147766

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9de9048d3cce"
down_revision = "2025012700"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop all constraints first
    op.execute(
        """
        -- Drop foreign key constraints
        ALTER TABLE news_articles DROP CONSTRAINT IF EXISTS news_articles_tenant_id_fkey CASCADE;
        ALTER TABLE strategies DROP CONSTRAINT IF EXISTS strategies_tenant_id_fkey CASCADE;
        ALTER TABLE tenant_configs DROP CONSTRAINT IF EXISTS tenant_configs_tenant_id_fkey CASCADE;
        ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_tenant_id_fkey CASCADE;
        ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_strategy_id_fkey CASCADE;
        ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_wallet_id_fkey CASCADE;
        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_tenant_id_fkey CASCADE;
        ALTER TABLE wallets DROP CONSTRAINT IF EXISTS wallets_tenant_id_fkey CASCADE;
        
        -- Drop unique constraints
        ALTER TABLE strategies DROP CONSTRAINT IF EXISTS uq_strategy_name CASCADE;
        ALTER TABLE wallets DROP CONSTRAINT IF EXISTS uq_wallet_address CASCADE;
        ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_user_email CASCADE;
        
        -- Drop indices that might depend on constraints
        DROP INDEX IF EXISTS idx_strategy_tenant;
        DROP INDEX IF EXISTS idx_wallet_tenant;
        DROP INDEX IF EXISTS idx_trade_tenant;
        DROP INDEX IF EXISTS idx_user_tenant;
    """
    )

    # Convert tenant_id columns to integer
    # Convert ID columns to integer and handle column rename
    op.execute(
        """
        -- Convert primary keys first
        ALTER TABLE tenants ALTER COLUMN id TYPE INTEGER USING id::integer;
        ALTER TABLE strategies ALTER COLUMN id TYPE INTEGER USING id::integer;
        
        -- Convert foreign keys next
        ALTER TABLE news_articles ALTER COLUMN tenant_id TYPE INTEGER USING tenant_id::integer;
        ALTER TABLE strategies ALTER COLUMN tenant_id TYPE INTEGER USING tenant_id::integer;
        ALTER TABLE tenant_configs ALTER COLUMN tenant_id TYPE INTEGER USING tenant_id::integer;
        ALTER TABLE trades ALTER COLUMN tenant_id TYPE INTEGER USING tenant_id::integer;
        ALTER TABLE trades ALTER COLUMN strategy_id TYPE INTEGER USING strategy_id::integer;
        ALTER TABLE users ALTER COLUMN tenant_id TYPE INTEGER USING tenant_id::integer;
        ALTER TABLE wallets ALTER COLUMN tenant_id TYPE INTEGER USING tenant_id::integer;
        
        -- Handle parameters -> config column rename
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'strategies' AND column_name = 'parameters'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'strategies' AND column_name = 'config'
            ) THEN
                ALTER TABLE strategies RENAME COLUMN parameters TO config;
            END IF;
        END$$;
    """
    )

    # Recreate foreign key constraints
    op.execute(
        """
        ALTER TABLE news_articles 
        ADD CONSTRAINT news_articles_tenant_id_fkey 
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        
        ALTER TABLE strategies 
        ADD CONSTRAINT strategies_tenant_id_fkey 
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        
        ALTER TABLE tenant_configs 
        ADD CONSTRAINT tenant_configs_tenant_id_fkey 
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        
        ALTER TABLE trades 
        ADD CONSTRAINT trades_tenant_id_fkey 
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        
        ALTER TABLE trades 
        ADD CONSTRAINT trades_strategy_id_fkey 
        FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE;
        
        ALTER TABLE users 
        ADD CONSTRAINT users_tenant_id_fkey 
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
        
        ALTER TABLE wallets 
        ADD CONSTRAINT wallets_tenant_id_fkey 
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """
    )
    op.create_table_comment(
        "news_articles",
        "Stores news articles for sentiment analysis",
        existing_comment=None,
        schema=None,
    )
    op.create_table_comment(
        "sentiment_analysis",
        "Stores sentiment analysis results",
        existing_comment=None,
        schema=None,
    )
    # Add config column and migrate data from parameters
    op.execute(
        """
        DO $$
        BEGIN
            -- Check if config column exists
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'strategies' 
                AND column_name = 'config'
            ) THEN
                -- Add config column if it doesn't exist
                ALTER TABLE strategies ADD COLUMN config JSONB;
            END IF;

            -- Update config from parameters if parameters exists
            IF EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'strategies' 
                AND column_name = 'parameters'
            ) THEN
                -- Copy data from parameters to config
                UPDATE strategies 
                SET config = parameters::jsonb 
                WHERE parameters IS NOT NULL;

                -- Drop parameters column
                ALTER TABLE strategies DROP COLUMN parameters;
            END IF;

            -- Make config not null
            ALTER TABLE strategies ALTER COLUMN config SET NOT NULL;
        END $$;
    """
    )

    op.execute(
        """
        ALTER TABLE strategies 
        ALTER COLUMN tenant_id TYPE INTEGER 
        USING tenant_id::integer
    """
    )
    # Create strategy type enum
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'strategytype') THEN
                CREATE TYPE strategytype AS ENUM (
                    'momentum', 'mean_reversion', 'breakout', 'trend_following',
                    'early_entry', 'batch_position', 'capital_rotation', 'social_sentiment',
                    'technical_analysis', 'automated_trading', 'copy_trading', 'market_making',
                    'multi_token_monitoring', 'stop_loss_take_profit'
                );
            END IF;
        END$$;
    """
    )

    # Convert strategy_type column
    op.execute(
        """
        ALTER TABLE strategies 
        ALTER COLUMN strategy_type TYPE strategytype 
        USING strategy_type::strategytype
    """
    )
    # Drop all constraints and indices in a single transaction
    op.execute(
        """
        BEGIN;
        
        -- Drop all foreign key constraints first
        ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_wallet_id_fkey CASCADE;
        ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_strategy_id_fkey CASCADE;
        ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_tenant_id_fkey CASCADE;
        ALTER TABLE strategies DROP CONSTRAINT IF EXISTS strategies_tenant_id_fkey CASCADE;
        ALTER TABLE news_articles DROP CONSTRAINT IF EXISTS news_articles_tenant_id_fkey CASCADE;
        ALTER TABLE tenant_configs DROP CONSTRAINT IF EXISTS tenant_configs_tenant_id_fkey CASCADE;
        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_tenant_id_fkey CASCADE;
        ALTER TABLE wallets DROP CONSTRAINT IF EXISTS wallets_tenant_id_fkey CASCADE;
        
        -- Drop all unique constraints
        ALTER TABLE strategies DROP CONSTRAINT IF EXISTS uq_strategy_name CASCADE;
        ALTER TABLE strategies DROP CONSTRAINT IF EXISTS uq_strategy_tenant_name CASCADE;
        ALTER TABLE wallets DROP CONSTRAINT IF EXISTS uq_wallet_address CASCADE;
        ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_user_email CASCADE;
        
        -- Drop all indices
        DROP INDEX IF EXISTS idx_strategy_active;
        DROP INDEX IF EXISTS idx_strategy_tenant;
        DROP INDEX IF EXISTS idx_strategy_type;
        DROP INDEX IF EXISTS idx_strategy_is_active;
        DROP INDEX IF EXISTS idx_strategy_tenant_type;
        DROP INDEX IF EXISTS idx_wallet_active;
        DROP INDEX IF EXISTS idx_wallet_chain;
        DROP INDEX IF EXISTS idx_wallet_tenant;
        DROP INDEX IF EXISTS idx_wallet_type;
        DROP INDEX IF EXISTS idx_wallet_address;
        DROP INDEX IF EXISTS idx_trade_tenant;
        DROP INDEX IF EXISTS idx_trade_strategy;
        DROP INDEX IF EXISTS idx_trade_wallet;
        
        COMMIT;
    """
    )

    # Create new indices and constraints
    op.create_index("idx_strategy_is_active", "strategies", ["is_active"], unique=False)
    op.create_index(
        "idx_strategy_tenant_type",
        "strategies",
        ["tenant_id", "strategy_type"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_strategy_tenant_name", "strategies", ["tenant_id", "name"]
    )
    op.create_table_comment(
        "strategies",
        "Stores trading strategy configurations",
        existing_comment=None,
        schema=None,
    )
    op.execute(
        "ALTER TABLE strategies DROP COLUMN IF EXISTS performance_metrics CASCADE"
    )
    op.execute(
        """
        ALTER TABLE tenant_configs 
        ALTER COLUMN tenant_id TYPE INTEGER 
        USING tenant_id::integer
    """
    )
    op.create_table_comment(
        "tenant_configs",
        "Stores tenant-specific configurations",
        existing_comment=None,
        schema=None,
    )
    op.alter_column(
        "tenants",
        "id",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.Integer(),
        existing_nullable=False,
        autoincrement=True,
        existing_server_default=sa.text("nextval('tenants_id_seq'::regclass)"),
    )
    op.create_table_comment(
        "tenants",
        "Stores multi-tenant organizations",
        existing_comment=None,
        schema=None,
    )
    op.execute(
        """
        ALTER TABLE trades 
        ALTER COLUMN tenant_id TYPE INTEGER 
        USING tenant_id::integer
    """
    )
    op.alter_column(
        "trades",
        "strategy_id",
        existing_type=sa.VARCHAR(length=50),
        type_=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "trades",
        "pair",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        "trades",
        "side",
        existing_type=sa.VARCHAR(length=10),
        type_=sa.String(length=4),
        existing_nullable=False,
    )
    # Create trade status enum
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tradestatus') THEN
                CREATE TYPE tradestatus AS ENUM (
                    'PENDING', 'OPEN', 'CLOSED', 'CANCELLED', 'FAILED'
                );
            END IF;
        END$$;
    """
    )

    # Convert status column
    op.execute(
        """
        ALTER TABLE trades 
        ALTER COLUMN status TYPE tradestatus 
        USING status::tradestatus
    """
    )
    op.alter_column(
        "trades",
        "trade_metadata",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        nullable=False,
    )
    op.drop_index("idx_trade_fee", table_name="trades")
    # Drop existing indices first
    op.execute(
        """
        DROP INDEX IF EXISTS idx_trade_filled;
        DROP INDEX IF EXISTS idx_trade_parent;
        DROP INDEX IF EXISTS idx_trade_remaining;
        DROP INDEX IF EXISTS idx_trade_status;
        DROP INDEX IF EXISTS idx_trade_take_profit;
    """
    )

    # Create new indices
    op.create_index(
        "idx_trade_created_at", "trades", [sa.text("created_at DESC")], unique=False
    )
    op.create_index("idx_trade_pair", "trades", ["pair"], unique=False)
    op.create_index(
        "idx_trade_tenant_pair", "trades", ["tenant_id", "pair"], unique=False
    )
    op.create_index(
        "idx_trade_tenant_status", "trades", ["tenant_id", "status"], unique=False
    )
    # Add unique constraint on wallets.address first
    op.execute(
        """
        ALTER TABLE wallets ADD CONSTRAINT uq_wallet_address UNIQUE (address);
    """
    )

    # Then create foreign key constraints
    op.create_foreign_key(
        None, "trades", "wallets", ["wallet_id"], ["address"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        None, "trades", "strategies", ["strategy_id"], ["id"], ondelete="CASCADE"
    )
    op.create_table_comment(
        "trades",
        "Stores trading transactions with support for partial fills and batch positions",
        existing_comment=None,
        schema=None,
    )
    op.execute(
        """
        ALTER TABLE users 
        ALTER COLUMN tenant_id TYPE INTEGER 
        USING tenant_id::integer
    """
    )
    op.create_table_comment(
        "users", "Stores tenant users", existing_comment=None, schema=None
    )
    op.execute(
        """
        ALTER TABLE wallets 
        ALTER COLUMN tenant_id TYPE INTEGER 
        USING tenant_id::integer
    """
    )
    # Drop all constraints and indices in correct order
    op.execute(
        """
        -- Drop foreign key constraints first
        ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_wallet_id_fkey CASCADE;
        ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_strategy_id_fkey CASCADE;
        ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_tenant_id_fkey CASCADE;
        
        -- Drop unique constraints
        ALTER TABLE wallets DROP CONSTRAINT IF EXISTS uq_wallet_address CASCADE;
        ALTER TABLE strategies DROP CONSTRAINT IF EXISTS uq_strategy_name CASCADE;
        
        -- Drop indices
        DROP INDEX IF EXISTS idx_wallet_active;
        DROP INDEX IF EXISTS idx_wallet_chain;
        DROP INDEX IF EXISTS idx_wallet_tenant;
        DROP INDEX IF EXISTS idx_wallet_type;
        DROP INDEX IF EXISTS idx_wallet_address;
    """
    )

    # Create new indices and constraints
    op.create_index("idx_wallet_address", "wallets", ["address"], unique=False)
    op.create_index(
        "idx_wallet_balance", "wallets", [sa.text("balance DESC")], unique=False
    )
    op.create_index(
        "idx_wallet_tenant_chain", "wallets", ["tenant_id", "chain"], unique=False
    )
    op.create_unique_constraint(
        "uq_wallet_tenant_address_chain", "wallets", ["tenant_id", "address", "chain"]
    )
    op.create_table_comment(
        "wallets", "Stores cryptocurrency wallets", existing_comment=None, schema=None
    )
    op.drop_column("wallets", "wallet_metadata")
    # ### end Alembic commands ###


def downgrade() -> None:
    # Handle config -> parameters column rename first
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'strategies' AND column_name = 'config'
            ) THEN
                ALTER TABLE strategies RENAME COLUMN config TO parameters;
            END IF;
        END$$;
    """
    )

    # Convert back to VARCHAR
    op.execute(
        """
        ALTER TABLE tenants ALTER COLUMN id TYPE VARCHAR(255) USING id::varchar;
        ALTER TABLE news_articles ALTER COLUMN tenant_id TYPE VARCHAR(255) USING tenant_id::varchar;
        ALTER TABLE strategies ALTER COLUMN tenant_id TYPE VARCHAR(255) USING tenant_id::varchar;
        ALTER TABLE tenant_configs ALTER COLUMN tenant_id TYPE VARCHAR(255) USING tenant_id::varchar;
        ALTER TABLE trades ALTER COLUMN tenant_id TYPE VARCHAR(255) USING tenant_id::varchar;
        ALTER TABLE trades ALTER COLUMN strategy_id TYPE VARCHAR(255) USING strategy_id::varchar;
        ALTER TABLE users ALTER COLUMN tenant_id TYPE VARCHAR(255) USING tenant_id::varchar;
        ALTER TABLE wallets ALTER COLUMN tenant_id TYPE VARCHAR(255) USING tenant_id::varchar;
    """
    )
    op.add_column(
        "wallets",
        sa.Column(
            "wallet_metadata",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.drop_table_comment(
        "wallets", existing_comment="Stores cryptocurrency wallets", schema=None
    )
    op.drop_constraint("uq_wallet_tenant_address_chain", "wallets", type_="unique")
    op.drop_index("idx_wallet_tenant_chain", table_name="wallets")
    op.drop_index("idx_wallet_balance", table_name="wallets")
    op.drop_index("idx_wallet_address", table_name="wallets")
    op.create_unique_constraint("uq_wallet_address", "wallets", ["address"])
    op.create_index("idx_wallet_type", "wallets", ["wallet_type"], unique=False)
    op.create_index("idx_wallet_tenant", "wallets", ["tenant_id"], unique=False)
    op.create_index("idx_wallet_chain", "wallets", ["chain"], unique=False)
    op.create_index("idx_wallet_active", "wallets", ["is_active"], unique=False)
    op.alter_column(
        "wallets",
        "tenant_id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )
    op.drop_table_comment("users", existing_comment="Stores tenant users", schema=None)
    op.alter_column(
        "users",
        "tenant_id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )
    op.drop_table_comment(
        "trades",
        existing_comment="Stores trading transactions with support for partial fills and batch positions",
        schema=None,
    )
    op.drop_constraint(None, "trades", type_="foreignkey")
    op.drop_constraint(None, "trades", type_="foreignkey")
    op.drop_index("idx_trade_tenant_status", table_name="trades")
    op.drop_index("idx_trade_tenant_pair", table_name="trades")
    op.drop_index("idx_trade_pair", table_name="trades")
    op.drop_index("idx_trade_created_at", table_name="trades")
    op.create_index("idx_trade_wallet", "trades", ["wallet_id"], unique=False)
    op.create_index("idx_trade_tenant", "trades", ["tenant_id"], unique=False)
    op.create_index("idx_trade_take_profit", "trades", ["take_profit"], unique=False)
    op.create_index("idx_trade_strategy", "trades", ["strategy_id"], unique=False)
    op.create_index("idx_trade_stop_loss", "trades", ["stop_loss"], unique=False)
    op.create_index("idx_trade_fee", "trades", ["fee"], unique=False)
    op.alter_column(
        "trades",
        "trade_metadata",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        nullable=True,
    )
    op.alter_column(
        "trades",
        "status",
        existing_type=sa.Enum(
            "PENDING", "OPEN", "CLOSED", "CANCELLED", "FAILED", name="tradestatus"
        ),
        type_=sa.VARCHAR(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        "trades",
        "side",
        existing_type=sa.String(length=4),
        type_=sa.VARCHAR(length=10),
        existing_nullable=False,
    )
    op.alter_column(
        "trades",
        "pair",
        existing_type=sa.String(length=20),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "trades",
        "strategy_id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(length=50),
        existing_nullable=False,
    )
    op.alter_column(
        "trades",
        "tenant_id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )
    op.drop_table_comment(
        "tenants", existing_comment="Stores multi-tenant organizations", schema=None
    )
    op.alter_column(
        "tenants",
        "id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
        autoincrement=True,
        existing_server_default=sa.text("nextval('tenants_id_seq'::regclass)"),
    )
    op.drop_table_comment(
        "tenant_configs",
        existing_comment="Stores tenant-specific configurations",
        schema=None,
    )
    op.alter_column(
        "tenant_configs",
        "tenant_id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )
    op.add_column(
        "strategies",
        sa.Column(
            "parameters",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "strategies",
        sa.Column(
            "performance_metrics",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.drop_table_comment(
        "strategies",
        existing_comment="Stores trading strategy configurations",
        schema=None,
    )
    op.drop_constraint("uq_strategy_tenant_name", "strategies", type_="unique")
    op.drop_index("idx_strategy_tenant_type", table_name="strategies")
    op.drop_index("idx_strategy_is_active", table_name="strategies")
    op.create_unique_constraint("uq_strategy_name", "strategies", ["tenant_id", "name"])
    op.create_index("idx_strategy_type", "strategies", ["strategy_type"], unique=False)
    op.create_index("idx_strategy_tenant", "strategies", ["tenant_id"], unique=False)
    op.create_index("idx_strategy_active", "strategies", ["is_active"], unique=False)
    op.alter_column(
        "strategies",
        "strategy_type",
        existing_type=sa.Enum(
            "MOMENTUM",
            "MEAN_REVERSION",
            "BREAKOUT",
            "TREND_FOLLOWING",
            "EARLY_ENTRY",
            "BATCH_POSITION",
            "CAPITAL_ROTATION",
            "SOCIAL_SENTIMENT",
            "TECHNICAL_ANALYSIS",
            "AUTOMATED_TRADING",
            "COPY_TRADING",
            "MARKET_MAKING",
            "MULTI_TOKEN_MONITORING",
            "STOP_LOSS_TAKE_PROFIT",
            name="strategytype",
        ),
        type_=sa.VARCHAR(length=50),
        existing_nullable=False,
    )
    op.alter_column(
        "strategies",
        "tenant_id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )
    op.drop_column("strategies", "config")
    op.drop_table_comment(
        "sentiment_analysis",
        existing_comment="Stores sentiment analysis results",
        schema=None,
    )
    op.drop_table_comment(
        "news_articles",
        existing_comment="Stores news articles for sentiment analysis",
        schema=None,
    )
    op.alter_column(
        "news_articles",
        "tenant_id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )
    # ### end Alembic commands ###
