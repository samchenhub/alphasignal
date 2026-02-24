"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Try to enable pgvector — silently skip if not installed on this host
    op.execute(sa.text("""
        DO $$
        BEGIN
            CREATE EXTENSION IF NOT EXISTS vector;
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END $$
    """))

    # Check whether pgvector actually loaded
    conn = op.get_bind()
    pgvector_ok = bool(
        conn.execute(
            sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).first()
    )

    op.create_table(
        "articles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("market", sa.String(5), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("url", sa.Text, nullable=False, unique=True),
        sa.Column("url_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("content", sa.Text),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("is_processed", sa.Boolean, default=False),
    )
    op.create_index("ix_articles_url_hash", "articles", ["url_hash"])
    op.create_index("ix_articles_is_processed", "articles", ["is_processed"])

    # Use Vector(1536) if pgvector is available, else JSONB as a placeholder
    if pgvector_ok:
        from pgvector.sqlalchemy import Vector
        embedding_col = sa.Column("embedding", Vector(1536))
    else:
        embedding_col = sa.Column("embedding", JSONB)

    op.create_table(
        "analysis_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "article_id",
            UUID(as_uuid=True),
            sa.ForeignKey("articles.id"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("market", sa.String(5), nullable=False),
        sa.Column("sentiment_score", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("entities", JSONB),
        sa.Column("summary", sa.Text),
        sa.Column("key_events", JSONB),
        embedding_col,
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("model_version", sa.String(50)),
    )
    op.create_index("ix_analysis_results_article_id", "analysis_results", ["article_id"])
    op.create_index("ix_analysis_results_ticker", "analysis_results", ["ticker"])

    # HNSW vector index — only when pgvector is available
    if pgvector_ok:
        op.execute(
            """
            CREATE INDEX ix_analysis_embedding_hnsw
            ON analysis_results
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        )

    op.create_table(
        "stock_prices",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("market", sa.String(5), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_price", sa.Float),
        sa.Column("volume", sa.BigInteger),
        sa.UniqueConstraint("ticker", "timestamp", name="uq_stock_prices_ticker_ts"),
    )
    op.create_index("ix_stock_prices_ticker", "stock_prices", ["ticker"])
    op.create_index("ix_stock_prices_timestamp", "stock_prices", ["timestamp"])

    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", UUID(as_uuid=True), sa.ForeignKey("articles.id")),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("is_sent", sa.Boolean, default=False),
    )
    op.create_index("ix_alerts_ticker", "alerts", ["ticker"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("stock_prices")
    op.drop_table("analysis_results")
    op.drop_table("articles")
    op.execute("DROP EXTENSION IF EXISTS vector")
