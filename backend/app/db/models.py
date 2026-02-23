import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.connection import Base


class Article(Base):
    """Raw ingested article — cold storage."""

    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    market: Mapped[str] = mapped_column(String(5))          # 'US' or 'CN'
    source: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(Text, unique=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    analyses: Mapped[list["AnalysisResult"]] = relationship(back_populates="article")


class AnalysisResult(Base):
    """LLM analysis output — hot query table."""

    __tablename__ = "analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id"), index=True
    )
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    market: Mapped[str] = mapped_column(String(5))

    sentiment_score: Mapped[float | None] = mapped_column(Float)   # -1.0 to 1.0
    confidence: Mapped[float | None] = mapped_column(Float)

    entities: Mapped[dict | None] = mapped_column(JSONB)
    # e.g. {"companies": ["Apple"], "tickers": ["AAPL"], "people": ["Tim Cook"]}

    summary: Mapped[str | None] = mapped_column(Text)
    key_events: Mapped[list | None] = mapped_column(JSONB)
    # e.g. [{"type": "earnings_warning", "description": "Revenue guidance cut 8%"}]

    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    model_version: Mapped[str | None] = mapped_column(String(50))

    article: Mapped["Article"] = relationship(back_populates="analyses")


class StockPrice(Base):
    """Time-aligned stock price data."""

    __tablename__ = "stock_prices"
    __table_args__ = (UniqueConstraint("ticker", "timestamp"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    market: Mapped[str] = mapped_column(String(5))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )
    close_price: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(BigInteger)


class UserWatchlist(Base):
    """Per-user ticker watchlist (Clerk user_id → ticker mapping)."""

    __tablename__ = "user_watchlists"
    __table_args__ = (UniqueConstraint("user_id", "ticker"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)  # Clerk sub
    ticker: Mapped[str] = mapped_column(String(20))
    market: Mapped[str] = mapped_column(String(10))  # 'US' | 'CN' | 'HK'
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Alert(Base):
    """Extreme sentiment events."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id")
    )
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    alert_type: Mapped[str] = mapped_column(String(50))
    # 'extreme_negative' | 'extreme_positive'
    message: Mapped[str] = mapped_column(Text)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
