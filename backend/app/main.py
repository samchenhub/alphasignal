"""
AlphaSignal — FastAPI Application Entry Point

Mounts all API routers and starts the APScheduler background scheduler.
On startup, triggers an immediate ingestion run so data appears quickly.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, news, search, sentiment, watchlist
from app.config import settings
from app.scheduler.tasks import create_scheduler, run_ingestion, run_price_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("AlphaSignal starting up...")

    scheduler = create_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler

    if not settings.skip_startup_sync:
        logger.info("Running initial ingestion on startup...")
        try:
            await run_ingestion()
            await run_price_sync(days_back=90)  # Bootstrap 90 days of price history
        except Exception as e:
            logger.warning("Initial ingestion failed (non-fatal): %s", e)
    else:
        logger.info("Skipping startup sync (SKIP_STARTUP_SYNC=true). Scheduler will handle it.")

    logger.info("AlphaSignal ready. API docs at http://localhost:8000/docs")

    yield  # ── Application running ──────────────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────────
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown(wait=False)
    logger.info("AlphaSignal shutdown complete.")


app = FastAPI(
    title="AlphaSignal",
    description="Real-time financial sentiment analysis engine powered by Claude AI",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the Next.js frontend (and local dev) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(sentiment.router)
app.include_router(news.router)
app.include_router(search.router)
app.include_router(alerts.router)
app.include_router(watchlist.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
