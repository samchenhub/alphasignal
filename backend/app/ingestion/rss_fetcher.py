"""
Universal RSS fetcher for US financial news sources.

Parses feeds, cleans HTML, deduplicates by URL hash,
and writes new articles to the database.
"""
import hashlib
import logging
from datetime import datetime, timezone

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Article

logger = logging.getLogger(__name__)

# Free, reliable US financial news RSS feeds
# Note: Reuters discontinued their free RSS feeds (~2020); replaced with NYT Business + Investing.com
US_RSS_FEEDS: list[dict] = [
    {
        "source": "NYT Business",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "market": "US",
    },
    {
        "source": "Yahoo Finance",
        "url": "https://finance.yahoo.com/news/rssindex",
        "market": "US",
    },
    {
        "source": "Seeking Alpha",
        "url": "https://seekingalpha.com/feed.xml",
        "market": "US",
    },
    {
        "source": "MarketWatch",
        "url": "https://feeds.marketwatch.com/marketwatch/topstories/",
        "market": "US",
    },
    {
        "source": "CNBC Finance",
        "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        "market": "US",
    },
]


def _url_hash(url: str) -> str:
    """SHA-256 of URL for fast dedup lookup."""
    return hashlib.sha256(url.encode()).hexdigest()


def _clean_html(raw: str) -> str:
    """Strip HTML tags, collapse whitespace, remove boilerplate."""
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "lxml")
    # Remove script/style blocks
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # Collapse multiple spaces/newlines
    import re
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_published(entry) -> datetime | None:
    """Extract publish time from a feedparser entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return None


async def fetch_feed(feed_cfg: dict, session: AsyncSession) -> int:
    """
    Fetch one RSS feed and persist new articles.
    Returns the number of new articles inserted.
    """
    source = feed_cfg["source"]
    url = feed_cfg["url"]
    market = feed_cfg["market"]

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            raw_content = response.content
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", source, exc)
        return 0

    parsed = feedparser.parse(raw_content)
    new_count = 0

    for entry in parsed.entries:
        article_url = getattr(entry, "link", None)
        if not article_url:
            continue

        url_hash = _url_hash(article_url)

        # Dedup check
        existing = await session.scalar(
            select(Article.id).where(Article.url_hash == url_hash)
        )
        if existing:
            continue

        # Extract content (summary or content field)
        raw_content_text = ""
        if hasattr(entry, "content") and entry.content:
            raw_content_text = entry.content[0].get("value", "")
        elif hasattr(entry, "summary"):
            raw_content_text = entry.summary or ""

        article = Article(
            market=market,
            source=source,
            url=article_url,
            url_hash=url_hash,
            title=_clean_html(getattr(entry, "title", "") or ""),
            content=_clean_html(raw_content_text),
            published_at=_parse_published(entry),
            is_processed=False,
        )
        session.add(article)
        new_count += 1

    if new_count > 0:
        await session.commit()
        logger.info("Ingested %d new articles from %s", new_count, source)

    return new_count


async def fetch_all_us_feeds(session: AsyncSession) -> int:
    """Fetch all configured US RSS feeds. Returns total new articles."""
    total = 0
    for feed_cfg in US_RSS_FEEDS:
        total += await fetch_feed(feed_cfg, session)
    return total
