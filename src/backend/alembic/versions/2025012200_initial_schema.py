"""Initial schema creation with enum types

Revision ID: 2025012200
Revises: 
Create Date: 2025-01-22 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision = "2025012200"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types first
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'newssource') THEN
                CREATE TYPE newssource AS ENUM ('COINDESK', 'COINTELEGRAPH', 'DECRYPT');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tenantstatus') THEN
                CREATE TYPE tenantstatus AS ENUM ('ACTIVE', 'SUSPENDED', 'DELETED');
            END IF;
        END$$;
    """
    )

    # Create tenants table first (no foreign keys)
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("api_key", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            ENUM(
                "ACTIVE", "SUSPENDED", "DELETED", name="tenantstatus", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key"),
    )
    op.create_index("idx_tenant_api_key", "tenants", ["api_key"])
    op.create_index("idx_tenant_status", "tenants", ["status"])

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )
    op.create_index("idx_user_tenant", "users", ["tenant_id"])
    op.create_index("idx_user_email", "users", ["email"])
    op.create_index("idx_user_active", "users", ["is_active"])

    # Create news_articles table
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "source",
            ENUM(
                "COINDESK",
                "COINTELEGRAPH",
                "DECRYPT",
                name="newssource",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("article_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_article_url"),
    )
    op.create_index("idx_article_tenant", "news_articles", ["tenant_id"])
    op.create_index("idx_article_source", "news_articles", ["source"])
    op.create_index(
        "idx_article_published", "news_articles", [sa.text("published_at DESC")]
    )

    # Create sentiment_analysis table
    op.create_table(
        "sentiment_analysis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("entities", sa.JSON(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["article_id"], ["news_articles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sentiment_article", "sentiment_analysis", ["article_id"])
    op.create_index("idx_sentiment_score", "sentiment_analysis", ["sentiment_score"])

    # Create trades table
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.String(length=255), nullable=False),
        sa.Column("pair", sa.String(length=255), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("price", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("filled_amount", sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column(
            "remaining_amount", sa.Numeric(precision=36, scale=18), nullable=True
        ),
        sa.Column("execution_price", sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("strategy_id", sa.String(length=50), nullable=False),
        sa.Column("parent_trade_id", sa.Integer(), nullable=True),
        sa.Column("trade_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_trade_id"], ["trades.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_trade_tenant", "trades", ["tenant_id"])
    op.create_index("idx_trade_wallet", "trades", ["wallet_id"])
    op.create_index("idx_trade_status", "trades", ["status"])
    op.create_index("idx_trade_strategy", "trades", ["strategy_id"])
    op.create_index("idx_trade_parent", "trades", ["parent_trade_id"])
    op.create_index("idx_trade_filled", "trades", ["filled_amount"])
    op.create_index("idx_trade_remaining", "trades", ["remaining_amount"])

    # Create wallets table
    op.create_table(
        "wallets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("wallet_type", sa.String(length=50), nullable=False),
        sa.Column("balance", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("wallet_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("address", name="uq_wallet_address"),
    )
    op.create_index("idx_wallet_tenant", "wallets", ["tenant_id"])
    op.create_index("idx_wallet_type", "wallets", ["wallet_type"])
    op.create_index("idx_wallet_active", "wallets", ["is_active"])

    # Create strategies table
    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("strategy_type", sa.String(length=50), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("performance_metrics", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_strategy_name"),
    )
    op.create_index("idx_strategy_tenant", "strategies", ["tenant_id"])
    op.create_index("idx_strategy_type", "strategies", ["strategy_type"])
    op.create_index("idx_strategy_active", "strategies", ["is_active"])

    # Create tenant_configs table
    op.create_table(
        "tenant_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("config_key", sa.String(length=255), nullable=False),
        sa.Column("config_value", sa.JSON(), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "config_key", name="uq_tenant_config_key"),
    )
    op.create_index("idx_config_tenant", "tenant_configs", ["tenant_id"])
    op.create_index("idx_config_key", "tenant_configs", ["config_key"])


def downgrade() -> None:
    # Get database connection
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Drop tables in reverse order of dependencies if they exist
    tables = [
        "tenant_configs",
        "trades",  # Drop trades before wallets due to parent_trade_id FK
        "wallets",
        "strategies",
        "sentiment_analysis",
        "news_articles",
        "users",
        "tenants",
    ]

    for table in tables:
        if inspector.has_table(table):
            op.drop_table(table)

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS newssource")
    op.execute("DROP TYPE IF EXISTS tenantstatus")
