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
    """Manually trigger news ingestion + price sync (runs in background, returns immediately)."""
    import asyncio
    _check_secret(x_admin_secret)

    async def _run():
        try:
            await run_ingestion()
            await run_price_sync(days_back=7)
            logger.info("Manual sync complete.")
        except Exception as e:
            logger.error("Manual sync failed: %s", e)

    asyncio.create_task(_run())
    return {"status": "ok", "message": "Sync started in background"}


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
    """Run LLM analysis on one recent article (processed or not) and return the full trace."""
    _check_secret(x_admin_secret)
    import asyncio
    from app.db.models import Article
    from app.analysis.claude_analyzer import _client, _is_relevant, _analyze, GROQ_MODEL

    async with AsyncSessionLocal() as session:
        total = (await session.execute(text("SELECT COUNT(*) FROM articles"))).scalar()
        unprocessed = (await session.execute(
            text("SELECT COUNT(*) FROM articles WHERE is_processed = false")
        )).scalar()

        if not _client:
            return {"error": "GROQ_API_KEY not configured", "total": total, "unprocessed": unprocessed}

        # Prefer unprocessed; fall back to any recent article so we can always test
        result = await session.execute(
            select(Article).where(Article.is_processed == False).limit(1)  # noqa: E712
        )
        article = result.scalar_one_or_none()
        if not article:
            result = await session.execute(
                select(Article).order_by(Article.fetched_at.desc()).limit(1)
            )
            article = result.scalar_one_or_none()

        if not article:
            return {"error": "No articles in DB", "total": total, "unprocessed": unprocessed}

        tickers = settings.us_ticker_list if article.market == "US" else settings.cn_ticker_list
        try:
            relevant = await asyncio.to_thread(_is_relevant, article.title or "", article.content or "", tickers)
            analysis = await asyncio.to_thread(_analyze, article.title or "", article.content or "", tickers, article.market) if relevant else None
            return {
                "total": total,
                "unprocessed": unprocessed,
                "article_is_already_processed": article.is_processed,
                "article_title": (article.title or "")[:100],
                "article_market": article.market,
                "tickers_checked": tickers,
                "is_relevant": relevant,
                "analysis_result": analysis,
            }
        except Exception as e:
            return {"error": str(e), "total": total, "unprocessed": unprocessed,
                    "article_title": (article.title or "")[:100]}


@router.post("/reset-unprocessed")
async def reset_unprocessed(limit: int = 20, x_admin_secret: str | None = Header(default=None)):
    """Mark the N most recent articles as unprocessed so they get re-analyzed."""
    _check_secret(x_admin_secret)
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            text(f"UPDATE articles SET is_processed = false WHERE id IN "
                 f"(SELECT id FROM articles ORDER BY fetched_at DESC LIMIT {limit})")
        )
        await session.commit()
        return {"reset": res.rowcount, "message": f"Reset {res.rowcount} articles to unprocessed"}


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
