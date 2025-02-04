"""Update tenant_id types to string

Revision ID: 2025012300
Revises: 2025012200
Create Date: 2025-01-23 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2025012300"
down_revision = "2025012200"
branch_labels = None
depends_on = None


def upgrade():
    # Drop all foreign key constraints
    op.drop_constraint("trades_tenant_id_fkey", "trades", type_="foreignkey")
    op.drop_constraint("wallets_tenant_id_fkey", "wallets", type_="foreignkey")
    op.drop_constraint("strategies_tenant_id_fkey", "strategies", type_="foreignkey")
    op.drop_constraint("users_tenant_id_fkey", "users", type_="foreignkey")
    op.drop_constraint(
        "news_articles_tenant_id_fkey", "news_articles", type_="foreignkey"
    )
    op.drop_constraint(
        "tenant_configs_tenant_id_fkey", "tenant_configs", type_="foreignkey"
    )

    # Update tenant_id columns to String(255)
    op.alter_column(
        "tenants",
        "id",
        existing_type=sa.Integer(),
        type_=sa.String(255),
        existing_nullable=False,
        postgresql_using="id::varchar",
    )

    op.alter_column(
        "trades",
        "tenant_id",
        existing_type=sa.Integer(),
        type_=sa.String(255),
        existing_nullable=False,
        postgresql_using="tenant_id::varchar",
    )

    op.alter_column(
        "wallets",
        "tenant_id",
        existing_type=sa.Integer(),
        type_=sa.String(255),
        existing_nullable=False,
        postgresql_using="tenant_id::varchar",
    )

    op.alter_column(
        "strategies",
        "tenant_id",
        existing_type=sa.Integer(),
        type_=sa.String(255),
        existing_nullable=False,
        postgresql_using="tenant_id::varchar",
    )

    op.alter_column(
        "users",
        "tenant_id",
        existing_type=sa.Integer(),
        type_=sa.String(255),
        existing_nullable=False,
        postgresql_using="tenant_id::varchar",
    )

    op.alter_column(
        "news_articles",
        "tenant_id",
        existing_type=sa.Integer(),
        type_=sa.String(255),
        existing_nullable=False,
        postgresql_using="tenant_id::varchar",
    )

    op.alter_column(
        "tenant_configs",
        "tenant_id",
        existing_type=sa.Integer(),
        type_=sa.String(255),
        existing_nullable=False,
        postgresql_using="tenant_id::varchar",
    )

    # Re-create all foreign key constraints
    op.create_foreign_key(
        "trades_tenant_id_fkey",
        "trades",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "wallets_tenant_id_fkey",
        "wallets",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "strategies_tenant_id_fkey",
        "strategies",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "users_tenant_id_fkey",
        "users",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "news_articles_tenant_id_fkey",
        "news_articles",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "tenant_configs_tenant_id_fkey",
        "tenant_configs",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    # Drop all foreign key constraints
    op.drop_constraint("trades_tenant_id_fkey", "trades", type_="foreignkey")
    op.drop_constraint("wallets_tenant_id_fkey", "wallets", type_="foreignkey")
    op.drop_constraint("strategies_tenant_id_fkey", "strategies", type_="foreignkey")
    op.drop_constraint("users_tenant_id_fkey", "users", type_="foreignkey")
    op.drop_constraint(
        "news_articles_tenant_id_fkey", "news_articles", type_="foreignkey"
    )
    op.drop_constraint(
        "tenant_configs_tenant_id_fkey", "tenant_configs", type_="foreignkey"
    )

    # Revert tenant_id columns to Integer
    op.alter_column(
        "tenants",
        "id",
        existing_type=sa.String(255),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="id::integer",
    )

    op.alter_column(
        "trades",
        "tenant_id",
        existing_type=sa.String(255),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="tenant_id::integer",
    )

    op.alter_column(
        "wallets",
        "tenant_id",
        existing_type=sa.String(255),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="tenant_id::integer",
    )

    op.alter_column(
        "strategies",
        "tenant_id",
        existing_type=sa.String(255),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="tenant_id::integer",
    )

    op.alter_column(
        "users",
        "tenant_id",
        existing_type=sa.String(255),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="tenant_id::integer",
    )

    op.alter_column(
        "news_articles",
        "tenant_id",
        existing_type=sa.String(255),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="tenant_id::integer",
    )

    op.alter_column(
        "tenant_configs",
        "tenant_id",
        existing_type=sa.String(255),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="tenant_id::integer",
    )

    # Re-create all foreign key constraints
    op.create_foreign_key(
        "trades_tenant_id_fkey",
        "trades",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "wallets_tenant_id_fkey",
        "wallets",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "strategies_tenant_id_fkey",
        "strategies",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "users_tenant_id_fkey",
        "users",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "news_articles_tenant_id_fkey",
        "news_articles",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "tenant_configs_tenant_id_fkey",
        "tenant_configs",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
