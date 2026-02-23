"""
GET /api/v1/news/{ticker}

Returns recent news articles for a ticker with LLM analysis attached.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db
from app.db.models import AnalysisResult, Article

router = APIRouter(prefix="/api/v1/news", tags=["news"])


class NewsItem(BaseModel):
    article_id: str
    ticker: str
    market: str
    source: str
    title: str
    url: str
    published_at: datetime | None
    sentiment_score: float | None
    confidence: float | None
    summary: str | None
    key_events: list | None
    entities: dict | None


@router.get("/{ticker}", response_model=list[NewsItem])
async def get_news_for_ticker(
    ticker: str,
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Return recent news articles and their LLM analysis for a specific ticker.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(AnalysisResult, Article)
        .join(Article, AnalysisResult.article_id == Article.id)
        .where(
            AnalysisResult.ticker == ticker.upper(),
            Article.published_at >= since,
        )
        .order_by(Article.published_at.desc())
        .limit(limit)
    )
    rows = result.all()

    return [
        NewsItem(
            article_id=str(article.id),
            ticker=analysis.ticker,
            market=analysis.market,
            source=article.source,
            title=article.title,
            url=article.url,
            published_at=article.published_at,
            sentiment_score=analysis.sentiment_score,
            confidence=analysis.confidence,
            summary=analysis.summary,
            key_events=analysis.key_events,
            entities=analysis.entities,
        )
        for analysis, article in rows
    ]


@router.get("/", response_model=list[NewsItem])
async def get_latest_news(
    market: str | None = Query(default=None, description="Filter by market: US, CN, HK"),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recently analyzed news across all tickers."""
    query = (
        select(AnalysisResult, Article)
        .join(Article, AnalysisResult.article_id == Article.id)
        .order_by(AnalysisResult.processed_at.desc())
        .limit(limit)
    )
    if market:
        query = query.where(AnalysisResult.market == market.upper())

    result = await db.execute(query)
    rows = result.all()

    return [
        NewsItem(
            article_id=str(article.id),
            ticker=analysis.ticker,
            market=analysis.market,
            source=article.source,
            title=article.title,
            url=article.url,
            published_at=article.published_at,
            sentiment_score=analysis.sentiment_score,
            confidence=analysis.confidence,
            summary=analysis.summary,
            key_events=analysis.key_events,
            entities=analysis.entities,
        )
        for analysis, article in rows
    ]
