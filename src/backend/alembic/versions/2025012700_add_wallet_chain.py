"""Add chain column to wallets table

Revision ID: 2025012700
Revises: 2025012600
Create Date: 2025-01-27 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2025012700"
down_revision = "2025012600"
branch_labels = None
depends_on = None


def upgrade():
    # Add chain column
    op.add_column(
        "wallets",
        sa.Column("chain", sa.String(50), nullable=False, server_default="solana"),
    )

    # Create index for chain column
    op.create_index("idx_wallet_chain", "wallets", ["chain"])


def downgrade():
    # Drop index first
    op.drop_index("idx_wallet_chain", table_name="wallets")

    # Drop column
    op.drop_column("wallets", "chain")
