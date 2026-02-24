"""
Admin endpoints for manual operations.
Protected by ADMIN_SECRET env var (skip protection when not set, for dev).
"""
import logging

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import func, select, text

from app.config import settings
from app.db.connection import AsyncSessionLocal
from app.scheduler.tasks import run_ingestion, run_price_sync

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _check_secret(x_admin_secret: str | None):
    if settings.admin_secret and x_admin_secret != settings.admin_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.post("/sync")
async def trigger_sync(x_admin_secret: str | None = Header(default=None)):
    """Manually trigger news ingestion + price sync."""
    _check_secret(x_admin_secret)
    try:
        await run_ingestion()
        await run_price_sync(days_back=7)
        return {"status": "ok", "message": "Sync triggered successfully"}
    except Exception as e:
        logger.error("Manual sync failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/llm-status")
async def llm_status():
    """Check if Groq is configured and test a live API call."""
    from app.analysis.claude_analyzer import _client, GROQ_MODEL
    key = settings.groq_api_key
    if not key:
        return {"key_set": False, "client_ready": False, "error": "GROQ_API_KEY not set"}
    if _client is None:
        return {"key_set": True, "client_ready": False, "error": "Client not initialized — redeploy needed"}
    try:
        import asyncio
        result = await asyncio.to_thread(
            _client.chat.completions.create,
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=10,
        )
        return {"key_set": True, "client_ready": True, "test_response": result.choices[0].message.content}
    except Exception as e:
        return {"key_set": True, "client_ready": True, "error": str(e)}


@router.get("/debug-analysis")
async def debug_analysis(x_admin_secret: str | None = Header(default=None)):
    """Run analysis on one unprocessed article and return raw result."""
    _check_secret(x_admin_secret)
    from sqlalchemy import select, text
    from app.db.models import Article
    from app.analysis.claude_analyzer import _client, _is_relevant, _analyze, GROQ_MODEL
    from app.config import settings

    async with AsyncSessionLocal() as session:
        # Count processed vs unprocessed
        total = (await session.execute(text("SELECT COUNT(*) FROM articles"))).scalar()
        unprocessed = (await session.execute(
            text("SELECT COUNT(*) FROM articles WHERE is_processed = false")
        )).scalar()

        if not _client:
            return {"error": "GROQ_API_KEY not configured", "total": total, "unprocessed": unprocessed}

        # Grab one unprocessed article
        result = await session.execute(
            select(Article).where(Article.is_processed == False).limit(1)  # noqa: E712
        )
        article = result.scalar_one_or_none()
        if not article:
            return {"error": "No unprocessed articles", "total": total, "unprocessed": unprocessed}

        tickers = settings.us_ticker_list if article.market == "US" else settings.cn_ticker_list
        import asyncio
        try:
            relevant = await asyncio.to_thread(_is_relevant, article.title or "", article.content or "", tickers)
            analysis = await asyncio.to_thread(_analyze, article.title or "", article.content or "", tickers, article.market) if relevant else None
            return {
                "total": total,
                "unprocessed": unprocessed,
                "article_title": article.title[:100],
                "article_market": article.market,
                "tickers_checked": tickers,
                "is_relevant": relevant,
                "analysis_result": analysis,
            }
        except Exception as e:
            return {"error": str(e), "total": total, "unprocessed": unprocessed, "article_title": article.title[:100]}


@router.get("/stats")
async def get_stats(x_admin_secret: str | None = Header(default=None)):
    """Return row counts for all tables — useful for diagnosing empty DB."""
    _check_secret(x_admin_secret)
    async with AsyncSessionLocal() as session:
        tables = ["articles", "analysis_results", "stock_prices", "alerts", "user_watchlists"]
        counts = {}
        for table in tables:
            try:
                result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                counts[table] = result.scalar()
            except Exception as e:
                counts[table] = f"error: {e}"
    return counts
