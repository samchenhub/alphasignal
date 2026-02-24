"""
POST /api/v1/backtest/         — parse strategy + run backtest
GET  /api/v1/backtest/history  — list recent backtests (last 20)
"""
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.strategy_parser import parse_strategy
from app.auth.dependencies import get_optional_user_id
from app.backtest.engine import run_backtest
from app.db.connection import get_db
from app.db.models import BacktestResult, BacktestStrategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


# ── Request / Response models ─────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    natural_language: str = Field(..., min_length=10, max_length=1000)
    ticker: str = Field(..., min_length=1, max_length=20)
    start_date: date = Field(default_factory=lambda: date.today() - timedelta(days=365))
    end_date: date = Field(default_factory=lambda: date.today())


class TradeEntry(BaseModel):
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    direction: str


class BacktestMetrics(BaseModel):
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int


class BacktestResponse(BaseModel):
    strategy_id: str
    ticker: str
    direction: str
    parsed_strategy: dict
    metrics: BacktestMetrics
    equity_curve: list[float]
    trade_log: list[TradeEntry]
    warning: str | None = None


class HistoryItem(BaseModel):
    strategy_id: str
    ticker: str
    natural_language_input: str
    total_return: float | None
    total_trades: int | None
    created_at: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=BacktestResponse)
async def run_backtest_endpoint(
    req: BacktestRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    Parse a natural language strategy and run it against historical data.
    """
    ticker = req.ticker.upper().strip()

    if req.start_date >= req.end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date.")

    # Step 1: Parse natural language → strategy JSON
    parsed = await parse_strategy(req.natural_language, ticker)

    if parsed.get("error"):
        raise HTTPException(
            status_code=422,
            detail=f"Could not parse strategy: {parsed['error']}",
        )

    # Use ticker from parsed strategy if available, otherwise fall back to request
    effective_ticker = parsed.get("ticker", ticker).upper()
    parsed["ticker"] = effective_ticker

    # Step 2: Persist strategy record
    strategy_record = BacktestStrategy(
        user_id=user_id,
        natural_language_input=req.natural_language,
        parsed_strategy=parsed,
        ticker=effective_ticker,
        start_date=req.start_date,
        end_date=req.end_date,
    )
    db.add(strategy_record)
    await db.flush()  # get the ID without committing

    # Step 3: Run backtest
    result_data = await run_backtest(
        strategy=parsed,
        session=db,
        start=req.start_date,
        end=req.end_date,
    )

    if result_data.get("error") and result_data.get("total_trades", 0) == 0:
        await db.rollback()
        raise HTTPException(status_code=422, detail=result_data["error"])

    # Step 4: Persist result
    result_record = BacktestResult(
        strategy_id=strategy_record.id,
        total_return=result_data["total_return"],
        sharpe_ratio=result_data["sharpe_ratio"],
        max_drawdown=result_data["max_drawdown"],
        win_rate=result_data["win_rate"],
        total_trades=result_data["total_trades"],
        equity_curve=result_data["equity_curve"],
        trade_log=result_data["trade_log"],
    )
    db.add(result_record)
    await db.commit()

    direction = parsed.get("direction", "long")

    return BacktestResponse(
        strategy_id=str(strategy_record.id),
        ticker=effective_ticker,
        direction=direction,
        parsed_strategy=parsed,
        metrics=BacktestMetrics(
            total_return=result_data["total_return"],
            sharpe_ratio=result_data["sharpe_ratio"],
            max_drawdown=result_data["max_drawdown"],
            win_rate=result_data["win_rate"],
            total_trades=result_data["total_trades"],
        ),
        equity_curve=result_data["equity_curve"],
        trade_log=[TradeEntry(**t) for t in result_data["trade_log"]],
        warning=result_data.get("error"),  # non-fatal warning (open position, etc.)
    )


@router.get("/history", response_model=list[HistoryItem])
async def get_backtest_history(
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """Return the 20 most recent backtests (filtered by user if authenticated)."""
    query = (
        select(BacktestStrategy, BacktestResult)
        .outerjoin(BacktestResult, BacktestResult.strategy_id == BacktestStrategy.id)
        .order_by(BacktestStrategy.created_at.desc())
        .limit(20)
    )
    if user_id:
        query = query.where(BacktestStrategy.user_id == user_id)

    result = await db.execute(query)
    rows = result.all()

    return [
        HistoryItem(
            strategy_id=str(strategy.id),
            ticker=strategy.ticker,
            natural_language_input=strategy.natural_language_input,
            total_return=bt_result.total_return if bt_result else None,
            total_trades=bt_result.total_trades if bt_result else None,
            created_at=strategy.created_at.isoformat(),
        )
        for strategy, bt_result in rows
    ]
