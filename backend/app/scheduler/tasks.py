"""
APScheduler task definitions.

Runs inside the FastAPI process — no separate worker needed.
Schedule:
  - Every N minutes: fetch RSS + CN news + SEC filings
  - After ingestion: run LLM analysis on unprocessed articles
  - Daily (market close): sync stock prices
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.db.connection import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def run_ingestion():
    """Fetch all news sources and run LLM analysis."""
    async with AsyncSessionLocal() as session:
        from app.ingestion.rss_fetcher import fetch_all_us_feeds
        from app.ingestion.akshare_news import fetch_cn_news, fetch_hk_news
        from app.ingestion.sec_edgar import fetch_sec_filings
        from app.ingestion.yfinance_news import fetch_all_ticker_news

        us_count = await fetch_all_us_feeds(session)
        yf_count = await fetch_all_ticker_news(session)
        cn_count = await fetch_cn_news(session)
        hk_count = await fetch_hk_news(session)
        sec_count = await fetch_sec_filings(session)

        total = us_count + yf_count + cn_count + hk_count + sec_count
        logger.info(
            "Ingestion complete: US RSS=%d, YF tickers=%d, CN=%d, HK=%d, SEC=%d (total=%d new articles)",
            us_count, yf_count, cn_count, hk_count, sec_count, total,
        )

    # Run LLM analysis on the newly ingested articles
    async with AsyncSessionLocal() as session:
        from app.analysis.claude_analyzer import process_unanalyzed_articles
        processed = await process_unanalyzed_articles(session, batch_size=50)
        logger.info("LLM analysis complete: %d articles processed", processed)


async def run_price_sync(days_back: int = 7):
    """Sync stock prices from yfinance and AKShare."""
    async with AsyncSessionLocal() as session:
        from app.prices.yfinance_client import sync_us_prices
        from app.prices.akshare_prices import sync_cn_prices

        us_rows = await sync_us_prices(session, days_back=days_back)
        cn_rows = await sync_cn_prices(session, days_back=days_back)
        logger.info("Price sync complete: US=%d rows, CN=%d rows", us_rows, cn_rows)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    # News ingestion + LLM analysis: every N minutes
    scheduler.add_job(
        run_ingestion,
        trigger="interval",
        minutes=settings.fetch_interval_minutes,
        id="ingestion",
        name="News ingestion + LLM analysis",
        max_instances=1,         # Prevent overlapping runs
        coalesce=True,
    )

    # Price sync: every hour (market data doesn't need minute-level updates for daily bars)
    scheduler.add_job(
        run_price_sync,
        trigger="interval",
        hours=1,
        id="price_sync",
        name="Stock price sync",
        max_instances=1,
        coalesce=True,
    )

    return scheduler
