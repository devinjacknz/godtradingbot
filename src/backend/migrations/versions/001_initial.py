"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-20 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'trader', 'viewer')")
    op.execute(
        "CREATE TYPE ordertype AS ENUM ('market', 'limit', 'stop_loss', 'take_profit')"
    )
    op.execute("CREATE TYPE orderside AS ENUM ('buy', 'sell')")
    op.execute(
        "CREATE TYPE orderstatus AS ENUM ('pending', 'open', 'filled', 'cancelled', 'failed')"
    )
    op.execute("CREATE TYPE risklevel AS ENUM ('low', 'medium', 'high')")
    op.execute(
        "CREATE TYPE alertlevel AS ENUM ('info', 'warning', 'error', 'critical')"
    )

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("admin", "trader", "viewer", name="userrole"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column(
            "preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("api_key", sa.String(), nullable=True),
        sa.Column("last_login", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_index(op.f("ix_users_api_key"), "users", ["api_key"], unique=True)

    # Create orders table
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "market", "limit", "stop_loss", "take_profit", name="ordertype"
            ),
            nullable=False,
        ),
        sa.Column(
            "side", postgresql.ENUM("buy", "sell", name="orderside"), nullable=False
        ),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "open", "filled", "cancelled", "failed", name="orderstatus"
            ),
            nullable=False,
        ),
        sa.Column("filled_quantity", sa.Float(), nullable=True),
        sa.Column("filled_price", sa.Float(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_orders_symbol"), "orders", ["symbol"], unique=False)
    op.create_index(
        op.f("ix_orders_external_id"), "orders", ["external_id"], unique=True
    )

    # Create positions table
    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column(
            "side", postgresql.ENUM("buy", "sell", name="orderside"), nullable=False
        ),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("liquidation_price", sa.Float(), nullable=True),
        sa.Column("leverage", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_positions_symbol"), "positions", ["symbol"], unique=False)

    # Create risk_limits table
    op.create_table(
        "risk_limits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("max_position_size", sa.Float(), nullable=False),
        sa.Column("max_leverage", sa.Float(), nullable=False),
        sa.Column("min_margin_level", sa.Float(), nullable=False),
        sa.Column("max_daily_loss", sa.Float(), nullable=False),
        sa.Column("max_drawdown_limit", sa.Float(), nullable=False),
        sa.Column("position_diversity_target", sa.Float(), nullable=False),
        sa.Column(
            "risk_level",
            postgresql.ENUM("low", "medium", "high", name="risklevel"),
            nullable=False,
        ),
        sa.Column(
            "custom_limits", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create alerts table
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "level",
            postgresql.ENUM("info", "warning", "error", "critical", name="alertlevel"),
            nullable=False,
        ),
        sa.Column("component", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    # Drop tables
    op.drop_table("alerts")
    op.drop_table("risk_limits")
    op.drop_table("positions")
    op.drop_table("orders")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE alertlevel")
    op.execute("DROP TYPE risklevel")
    op.execute("DROP TYPE orderstatus")
    op.execute("DROP TYPE orderside")
    op.execute("DROP TYPE ordertype")
    op.execute("DROP TYPE userrole")
