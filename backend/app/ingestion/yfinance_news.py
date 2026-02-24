"""
Per-ticker news ingestion via yfinance.

Fetches the latest ~10 news articles for each tracked US ticker directly
from Yahoo Finance. Unlike the general RSS feeds, every article here is
guaranteed to be about a tracked company, giving a much higher hit rate
for the LLM relevance filter.
"""
import hashlib
import logging
from datetime import datetime, timezone

import yfinance as yf
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.db.models import Article

logger = logging.getLogger(__name__)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


async def fetch_ticker_news(ticker: str, session: AsyncSession) -> int:
    """Fetch recent news for one ticker and persist new articles. Returns new article count."""
    try:
        import asyncio
        news_items = await asyncio.to_thread(lambda: yf.Ticker(ticker).news)
    except Exception as e:
        logger.warning("yfinance news fetch failed for %s: %s", ticker, e)
        return 0

    new_count = 0
    for item in news_items or []:
        content = item.get("content", {})
        url = content.get("canonicalUrl", {}).get("url") or content.get("clickThroughUrl", {}).get("url")
        if not url:
            continue

        url_hash = _url_hash(url)
        existing = await session.scalar(select(Article.id).where(Article.url_hash == url_hash))
        if existing:
            continue

        # Parse publication date
        pub_date = None
        pub_str = content.get("pubDate")
        if pub_str:
            try:
                pub_date = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            except Exception:
                pass

        title = content.get("title", "")
        summary = content.get("summary") or content.get("description") or ""
        publisher = content.get("provider", {}).get("displayName", "Yahoo Finance")

        article = Article(
            market="US",
            source=f"Yahoo Finance ({ticker})",
            url=url,
            url_hash=url_hash,
            title=title,
            content=summary,
            published_at=pub_date,
            is_processed=False,
        )
        session.add(article)
        new_count += 1

    if new_count > 0:
        await session.commit()
        logger.info("Ingested %d new articles for %s via yfinance", new_count, ticker)

    return new_count


async def fetch_all_ticker_news(session: AsyncSession) -> int:
    """Fetch news for all tracked US tickers. Returns total new articles."""
    tickers = settings.us_ticker_list
    total = 0
    for ticker in tickers:
        total += await fetch_ticker_news(ticker, session)
    return total
