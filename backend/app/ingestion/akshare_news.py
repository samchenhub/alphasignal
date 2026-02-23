"""
A-share and Hong Kong market news ingestion via AKShare.

AKShare wraps Eastmoney (东方财富), Sina Finance, and other
Chinese financial data sources for free.
"""
import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Article

logger = logging.getLogger(__name__)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


async def fetch_cn_news(session: AsyncSession, max_articles: int = 50) -> int:
    """
    Fetch latest A-share financial news from Eastmoney via AKShare.
    AKShare calls are synchronous, so we run them in a thread pool.
    """
    import asyncio

    try:
        import akshare as ak
    except ImportError:
        logger.error("AKShare not installed. Run: uv add akshare")
        return 0

    def _fetch_sync():
        # 东方财富财经新闻
        try:
            df = ak.stock_news_em(symbol="东方财富")
            return df
        except Exception as e:
            logger.warning("AKShare eastmoney news failed: %s", e)
            return None

    loop = asyncio.get_running_loop()
    df = await loop.run_in_executor(None, _fetch_sync)

    if df is None or df.empty:
        return 0

    # Log actual columns on first run to help diagnose mismatches
    logger.debug("AKShare CN news columns: %s", list(df.columns))

    new_count = 0
    for _, row in df.head(max_articles).iterrows():
        # AKShare column names: 新闻链接, 新闻标题, 新闻内容, 发布时间
        url = str(row.get("新闻链接", row.get("url", "")))
        title = str(row.get("新闻标题", row.get("title", "")))
        content = str(row.get("新闻内容", row.get("content", "")))
        pub_str = str(row.get("发布时间", row.get("datetime", "")))

        if not url or url == "nan":
            continue

        url_hash = _url_hash(url)
        existing = await session.scalar(
            select(Article.id).where(Article.url_hash == url_hash)
        )
        if existing:
            continue

        # Parse published_at
        published_at = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                published_at = datetime.strptime(pub_str, fmt).replace(
                    tzinfo=timezone.utc
                )
                break
            except (ValueError, TypeError):
                continue

        article = Article(
            market="CN",
            source="东方财富",
            url=url,
            url_hash=url_hash,
            title=title[:500],
            content=content[:5000] if content != "nan" else None,
            published_at=published_at,
            is_processed=False,
        )
        session.add(article)
        new_count += 1

    if new_count > 0:
        await session.commit()
        logger.info("Ingested %d new CN articles from 东方财富", new_count)

    return new_count


async def fetch_hk_news(session: AsyncSession, max_articles: int = 30) -> int:
    """Fetch Hong Kong market news. Uses Eastmoney HK news if available."""
    import asyncio

    try:
        import akshare as ak
    except ImportError:
        return 0

    def _fetch_sync():
        try:
            df = ak.stock_news_em(symbol="港股")
            return df
        except Exception as e:
            logger.warning("AKShare HK news failed: %s", e)
            return None

    loop = asyncio.get_running_loop()
    df = await loop.run_in_executor(None, _fetch_sync)

    if df is None or df.empty:
        return 0

    logger.debug("AKShare HK news columns: %s", list(df.columns))

    new_count = 0
    for _, row in df.head(max_articles).iterrows():
        url = str(row.get("新闻链接", row.get("url", "")))
        title = str(row.get("新闻标题", row.get("title", "")))

        if not url or url == "nan":
            continue

        url_hash = _url_hash(url)
        existing = await session.scalar(
            select(Article.id).where(Article.url_hash == url_hash)
        )
        if existing:
            continue

        article = Article(
            market="HK",
            source="东方财富港股",
            url=url,
            url_hash=url_hash,
            title=title[:500],
            content=None,
            is_processed=False,
        )
        session.add(article)
        new_count += 1

    if new_count > 0:
        await session.commit()
        logger.info("Ingested %d new HK articles", new_count)

    return new_count
