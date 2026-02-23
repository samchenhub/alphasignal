"""
GET /api/v1/alerts

Returns extreme sentiment events (high confidence, high magnitude scores).
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db
from app.db.models import Alert

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


class AlertItem(BaseModel):
    id: str
    ticker: str
    alert_type: str
    message: str
    triggered_at: datetime
    is_sent: bool


@router.get("/", response_model=list[AlertItem])
async def get_alerts(
    days: int = Query(default=7, ge=1, le=90),
    ticker: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return recent extreme sentiment alerts."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(Alert)
        .where(Alert.triggered_at >= since)
        .order_by(Alert.triggered_at.desc())
        .limit(100)
    )
    if ticker:
        query = query.where(Alert.ticker == ticker.upper())

    result = await db.execute(query)
    alerts = result.scalars().all()

    return [
        AlertItem(
            id=str(a.id),
            ticker=a.ticker,
            alert_type=a.alert_type,
            message=a.message,
            triggered_at=a.triggered_at,
            is_sent=a.is_sent,
        )
        for a in alerts
    ]
