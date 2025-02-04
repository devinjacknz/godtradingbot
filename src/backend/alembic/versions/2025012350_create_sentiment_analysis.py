"""Create sentiment analysis table

Revision ID: 2025012350
Revises: 2025012300
Create Date: 2025-01-23 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2025012350"
down_revision = "2025012300"
branch_labels = None
depends_on = None


def upgrade():
    # Get database connection
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Create sentiment_analysis table if it doesn't exist
    if not inspector.has_table("sentiment_analysis"):
        op.create_table(
            "sentiment_analysis",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.String(255), nullable=False),
            sa.Column("token_symbol", sa.String(50), nullable=False),
            sa.Column("source", sa.String(50), nullable=False),
            sa.Column("sentiment_score", sa.Float(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("mention_count", sa.Integer(), nullable=False),
            sa.Column("analyzed_at", sa.DateTime(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

        # Create indices
        op.create_index(
            "idx_sentiment_tenant", "sentiment_analysis", ["tenant_id"], unique=False
        )
        op.create_index(
            "idx_sentiment_token",
            "sentiment_analysis",
            ["token_symbol", "analyzed_at"],
            unique=False,
        )
        op.create_index(
            "idx_sentiment_analyzed",
            "sentiment_analysis",
            ["analyzed_at"],
            unique=False,
        )


def downgrade():
    # Get database connection
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check if table exists first
    if inspector.has_table("sentiment_analysis"):
        # Drop indices if they exist
        indices = inspector.get_indexes("sentiment_analysis")
        index_names = [index["name"] for index in indices]

        if "idx_sentiment_analyzed" in index_names:
            op.drop_index("idx_sentiment_analyzed", table_name="sentiment_analysis")
        if "idx_sentiment_token" in index_names:
            op.drop_index("idx_sentiment_token", table_name="sentiment_analysis")
        if "idx_sentiment_tenant" in index_names:
            op.drop_index("idx_sentiment_tenant", table_name="sentiment_analysis")

        # Drop table
        op.drop_table("sentiment_analysis")
