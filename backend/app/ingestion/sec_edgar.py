"""
SEC EDGAR RSS feed ingestion.

Monitors the latest 8-K (material events) and 10-Q (quarterly reports)
filings from EDGAR's public RSS feeds. No API key required.
"""
import hashlib
import logging
from datetime import datetime, timezone

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Article

logger = logging.getLogger(__name__)

# EDGAR full-text RSS — most recent filings across all companies
EDGAR_FEEDS = [
    {
        "source": "SEC EDGAR 8-K",
        "url": "https://efts.sec.gov/LATEST/search-index?q=%228-K%22&dateRange=custom&startdt=2024-01-01&forms=8-K",
        "market": "US",
    },
]

# Simpler: EDGAR's standard RSS for recent filings
EDGAR_RSS_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&search_text=&output=atom"


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


async def fetch_sec_filings(session: AsyncSession) -> int:
    """
    Fetch latest 8-K filings from SEC EDGAR RSS.
    These are the most market-moving events (earnings, M&A, guidance changes).
    """
    headers = {
        "User-Agent": "AlphaSignal research@alphasignal.dev",  # EDGAR requires UA
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            response = await client.get(EDGAR_RSS_URL)
            response.raise_for_status()
    except Exception as exc:
        logger.warning("Failed to fetch SEC EDGAR RSS: %s", exc)
        return 0

    parsed = feedparser.parse(response.content)
    new_count = 0

    for entry in parsed.entries:
        url = getattr(entry, "link", None)
        if not url:
            continue

        url_hash = _url_hash(url)
        existing = await session.scalar(
            select(Article.id).where(Article.url_hash == url_hash)
        )
        if existing:
            continue

        title = getattr(entry, "title", "SEC Filing")
        summary = getattr(entry, "summary", None) or ""

        # Parse date
        published_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

        article = Article(
            market="US",
            source="SEC EDGAR",
            url=url,
            url_hash=url_hash,
            title=title,
            content=summary,
            published_at=published_at,
            is_processed=False,
        )
        session.add(article)
        new_count += 1

    if new_count > 0:
        await session.commit()
        logger.info("Ingested %d new SEC EDGAR filings", new_count)

    return new_count
