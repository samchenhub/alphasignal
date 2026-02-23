"""
Watchlist API — per-user ticker subscriptions.

GET    /api/v1/watchlist/         — list the authenticated user's watchlist
POST   /api/v1/watchlist/         — add a ticker
DELETE /api/v1/watchlist/{ticker} — remove a ticker

All endpoints require a valid Clerk JWT (Authorization: Bearer <token>).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_user_id
from app.db.connection import get_db
from app.db.models import UserWatchlist

router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])


class WatchlistItem(BaseModel):
    ticker: str
    market: str
    added_at: str


class AddTickerRequest(BaseModel):
    ticker: str
    market: str = "US"  # 'US' | 'CN' | 'HK'


@router.get("/", response_model=list[WatchlistItem])
async def list_watchlist(
    user_id: str = Depends(require_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return all tickers in the authenticated user's watchlist."""
    result = await db.execute(
        select(UserWatchlist)
        .where(UserWatchlist.user_id == user_id)
        .order_by(UserWatchlist.added_at.desc())
    )
    rows = result.scalars().all()
    return [
        WatchlistItem(
            ticker=row.ticker,
            market=row.market,
            added_at=row.added_at.isoformat(),
        )
        for row in rows
    ]


@router.post("/", response_model=WatchlistItem, status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    body: AddTickerRequest,
    user_id: str = Depends(require_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Add a ticker to the authenticated user's watchlist."""
    ticker = body.ticker.upper()
    market = body.market.upper()

    # Check for duplicate
    existing = await db.execute(
        select(UserWatchlist).where(
            UserWatchlist.user_id == user_id,
            UserWatchlist.ticker == ticker,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{ticker} is already in your watchlist",
        )

    entry = UserWatchlist(user_id=user_id, ticker=ticker, market=market)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    return WatchlistItem(
        ticker=entry.ticker,
        market=entry.market,
        added_at=entry.added_at.isoformat(),
    )


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    ticker: str,
    user_id: str = Depends(require_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove a ticker from the authenticated user's watchlist."""
    result = await db.execute(
        delete(UserWatchlist).where(
            UserWatchlist.user_id == user_id,
            UserWatchlist.ticker == ticker.upper(),
        )
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{ticker.upper()} not found in your watchlist",
        )
