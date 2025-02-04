"""Add sentiment analysis table

Revision ID: 20240123_001
Revises: 
Create Date: 2024-01-23 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = "20240123_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sentiment_analysis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("sentiment", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("raw_score", JSON),
        sa.Column("analysis_metadata", JSON),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("news_article_id", sa.Integer(), nullable=True),
        sa.Column("social_post_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["news_article_id"],
            ["raw_news.id"],
        ),
        sa.ForeignKeyConstraint(
            ["social_post_id"],
            ["raw_social.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sentiment_analysis_source",
        "sentiment_analysis",
        ["source_type", "source_id"],
        unique=False,
    )
    op.create_index(
        "ix_sentiment_analysis_created_at",
        "sentiment_analysis",
        ["created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_sentiment_analysis_created_at")
    op.drop_index("ix_sentiment_analysis_source")
    op.drop_table("sentiment_analysis")
