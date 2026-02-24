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
