"""
GET /api/v1/sentiment/{ticker}

Returns time-series sentiment scores for a given ticker,
aligned with stock price data for frontend chart overlay.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db
from app.db.models import AnalysisResult, Article, StockPrice

router = APIRouter(prefix="/api/v1/sentiment", tags=["sentiment"])


class SentimentPoint(BaseModel):
    timestamp: datetime
    sentiment_score: float
    confidence: float
    ticker: str
    summary: str | None
    article_title: str | None


class PriceSentimentPoint(BaseModel):
    timestamp: datetime
    close_price: float | None
    sentiment_score: float | None
    confidence: float | None


@router.get("/{ticker}", response_model=list[SentimentPoint])
async def get_sentiment_history(
    ticker: str,
    days: int = Query(default=7, ge=1, le=365),
    market: str = Query(default="US"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return sentiment scores for a ticker over the past N days.
    Each point corresponds to one analyzed article.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(AnalysisResult, Article)
        .join(Article, AnalysisResult.article_id == Article.id)
        .where(
            AnalysisResult.ticker == ticker.upper(),
            AnalysisResult.processed_at >= since,
        )
        .order_by(AnalysisResult.processed_at.desc())
        .limit(200)
    )
    rows = result.all()

    if not rows:
        return []

    return [
        SentimentPoint(
            timestamp=analysis.processed_at,
            sentiment_score=analysis.sentiment_score or 0.0,
            confidence=analysis.confidence or 0.0,
            ticker=analysis.ticker,
            summary=analysis.summary,
            article_title=article.title,
        )
        for analysis, article in rows
    ]


@router.get("/{ticker}/price-correlation", response_model=list[PriceSentimentPoint])
async def get_price_sentiment_correlation(
    ticker: str,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """
    Return aligned price + daily average sentiment for chart overlay.
    Prices are bucketed by day; sentiment is the daily mean score.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    ticker = ticker.upper()

    # Fetch prices
    price_result = await db.execute(
        select(StockPrice)
        .where(StockPrice.ticker == ticker, StockPrice.timestamp >= since)
        .order_by(StockPrice.timestamp.asc())
    )
    prices = price_result.scalars().all()

    # Fetch sentiment scores
    sentiment_result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.ticker == ticker, AnalysisResult.processed_at >= since)
        .order_by(AnalysisResult.processed_at.asc())
    )
    sentiments = sentiment_result.scalars().all()

    # Build date → daily avg sentiment map
    from collections import defaultdict
    daily_sentiment: dict[str, list[float]] = defaultdict(list)
    for s in sentiments:
        if s.sentiment_score is not None:
            day_key = s.processed_at.strftime("%Y-%m-%d")
            daily_sentiment[day_key].append(s.sentiment_score)

    avg_sentiment = {
        day: sum(scores) / len(scores)
        for day, scores in daily_sentiment.items()
    }

    # Merge with price data
    points = []
    for price in prices:
        day_key = price.timestamp.strftime("%Y-%m-%d")
        points.append(
            PriceSentimentPoint(
                timestamp=price.timestamp,
                close_price=price.close_price,
                sentiment_score=avg_sentiment.get(day_key),
                confidence=None,
            )
        )

    return points
