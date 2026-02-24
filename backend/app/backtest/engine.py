"""
Backtest Engine — Pure Python + pandas

Simulates a sentiment-based trading strategy against historical
price and sentiment data stored in the database.

Supports:
  - Long / short direction
  - Sentiment threshold entry (e.g., sentiment < -0.7 → enter short)
  - Time-based exit (hold N trading days, then close)
  - Initial capital: $10,000
"""
import logging
import math
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnalysisResult, StockPrice

logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 10_000.0


# ── Data helpers ──────────────────────────────────────────────────────────────

async def _load_daily_sentiment(
    session: AsyncSession,
    ticker: str,
    start: date,
    end: date,
) -> dict[date, float]:
    """Return {date: avg_sentiment_score} for the given ticker and date range."""
    from datetime import datetime, timezone

    start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_dt = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=timezone.utc)

    result = await session.execute(
        select(AnalysisResult)
        .where(
            AnalysisResult.ticker == ticker.upper(),
            AnalysisResult.processed_at >= start_dt,
            AnalysisResult.processed_at <= end_dt,
            AnalysisResult.sentiment_score.is_not(None),
        )
        .order_by(AnalysisResult.processed_at.asc())
    )
    rows = result.scalars().all()

    daily: dict[date, list[float]] = defaultdict(list)
    for row in rows:
        d = row.processed_at.date()
        daily[d].append(row.sentiment_score)

    return {d: sum(scores) / len(scores) for d, scores in daily.items()}


async def _load_daily_prices(
    session: AsyncSession,
    ticker: str,
    start: date,
    end: date,
) -> dict[date, float]:
    """Return {date: close_price} for the given ticker and date range."""
    from datetime import datetime, timezone

    start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_dt = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=timezone.utc)

    result = await session.execute(
        select(StockPrice)
        .where(
            StockPrice.ticker == ticker.upper(),
            StockPrice.timestamp >= start_dt,
            StockPrice.timestamp <= end_dt,
            StockPrice.close_price.is_not(None),
        )
        .order_by(StockPrice.timestamp.asc())
    )
    rows = result.scalars().all()

    prices: dict[date, float] = {}
    for row in rows:
        d = row.timestamp.date()
        prices[d] = row.close_price

    return prices


# ── Strategy evaluation ───────────────────────────────────────────────────────

def _check_entry(
    entry_cfg: dict,
    sentiment_on_day: float | None,
) -> bool:
    """Return True if the entry condition is met."""
    if sentiment_on_day is None:
        return False

    operator = entry_cfg.get("operator", "<")
    threshold = float(entry_cfg.get("threshold", -0.7))

    if operator in ("<", "lt"):
        return sentiment_on_day < threshold
    if operator in (">", "gt"):
        return sentiment_on_day > threshold
    if operator in ("<=", "lte"):
        return sentiment_on_day <= threshold
    if operator in (">=", "gte"):
        return sentiment_on_day >= threshold
    return False


# ── Metrics calculation ───────────────────────────────────────────────────────

def _calculate_sharpe(daily_returns: list[float], annualisation: int = 252) -> float:
    """Annualised Sharpe ratio assuming risk-free rate = 0."""
    if len(daily_returns) < 2:
        return 0.0
    n = len(daily_returns)
    mean = sum(daily_returns) / n
    variance = sum((r - mean) ** 2 for r in daily_returns) / (n - 1)
    std = math.sqrt(variance) if variance > 0 else 0.0
    if std == 0:
        return 0.0
    return (mean / std) * math.sqrt(annualisation)


def _calculate_max_drawdown(equity: list[float]) -> float:
    """Maximum peak-to-trough drawdown as a negative fraction."""
    if len(equity) < 2:
        return 0.0
    peak = equity[0]
    max_dd = 0.0
    for val in equity:
        if val > peak:
            peak = val
        dd = (val - peak) / peak
        if dd < max_dd:
            max_dd = dd
    return max_dd


# ── Main engine ───────────────────────────────────────────────────────────────

async def run_backtest(
    strategy: dict,
    session: AsyncSession,
    start: date,
    end: date,
) -> dict:
    """
    Execute a backtest and return performance metrics.

    strategy schema:
        {
            "ticker": "NVDA",
            "direction": "long" | "short",
            "entry": {"metric": "sentiment_score", "operator": "<", "threshold": -0.7},
            "exit": {"type": "time_based", "holding_days": 5}
        }

    Returns:
        {
            "total_return": float,
            "sharpe_ratio": float,
            "max_drawdown": float,
            "win_rate": float,
            "total_trades": int,
            "equity_curve": [float, ...],
            "trade_log": [{"entry_date", "exit_date", "entry_price", "exit_price", "pnl_pct", "direction"}, ...],
            "error": str | None
        }
    """
    ticker = strategy.get("ticker", "").upper()
    direction = strategy.get("direction", "long").lower()
    entry_cfg = strategy.get("entry", {})
    exit_cfg = strategy.get("exit", {})
    holding_days = int(exit_cfg.get("holding_days", 5))

    if not ticker:
        return {"error": "No ticker specified in strategy."}

    # Load data
    sentiment_map = await _load_daily_sentiment(session, ticker, start, end)
    price_map = await _load_daily_prices(session, ticker, start, end)

    if len(price_map) < 5:
        return {
            "error": f"Not enough price data for {ticker} in the selected period. "
                     f"Try a different date range or check if {ticker} has historical data."
        }

    # Build sorted list of trading days (union of price + sentiment dates)
    all_days = sorted(price_map.keys())

    if len(all_days) < holding_days + 1:
        return {"error": "Not enough trading days in the selected period to run a backtest."}

    # ── Simulation ────────────────────────────────────────────────────────────
    capital = INITIAL_CAPITAL
    equity_curve: list[float] = [capital]
    trade_log: list[dict] = []
    daily_returns: list[float] = []

    in_position = False
    entry_day_idx: int = 0
    entry_price: float = 0.0

    for i, current_day in enumerate(all_days):
        price_today = price_map.get(current_day)
        if price_today is None:
            continue

        if not in_position:
            # Check entry condition
            sentiment_today = sentiment_map.get(current_day)
            if _check_entry(entry_cfg, sentiment_today):
                in_position = True
                entry_day_idx = i
                entry_price = price_today

        elif in_position:
            # Check exit condition (time-based)
            days_held = i - entry_day_idx
            if days_held >= holding_days:
                exit_price = price_today

                # Calculate P&L
                if direction == "long":
                    pnl_pct = (exit_price - entry_price) / entry_price
                else:  # short
                    pnl_pct = (entry_price - exit_price) / entry_price

                capital *= (1.0 + pnl_pct)
                daily_returns.append(pnl_pct)
                equity_curve.append(round(capital, 2))

                trade_log.append({
                    "entry_date": str(all_days[entry_day_idx]),
                    "exit_date": str(current_day),
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "pnl_pct": round(pnl_pct * 100, 2),
                    "direction": direction,
                })

                in_position = False
                entry_price = 0.0

    # Close any open position at last available price
    if in_position and len(all_days) > entry_day_idx:
        last_day = all_days[-1]
        last_price = price_map.get(last_day, entry_price)
        if direction == "long":
            pnl_pct = (last_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - last_price) / entry_price
        capital *= (1.0 + pnl_pct)
        daily_returns.append(pnl_pct)
        equity_curve.append(round(capital, 2))
        trade_log.append({
            "entry_date": str(all_days[entry_day_idx]),
            "exit_date": str(last_day) + " (open)",
            "entry_price": round(entry_price, 4),
            "exit_price": round(last_price, 4),
            "pnl_pct": round(pnl_pct * 100, 2),
            "direction": direction,
        })

    total_trades = len(trade_log)

    if total_trades == 0:
        return {
            "error": (
                f"No trades were triggered. The entry condition was never met for {ticker} "
                f"in the selected period. Try adjusting the threshold or date range."
            ),
            "total_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "equity_curve": [INITIAL_CAPITAL],
            "trade_log": [],
        }

    winning_trades = sum(1 for t in trade_log if t["pnl_pct"] > 0)
    total_return = (capital - INITIAL_CAPITAL) / INITIAL_CAPITAL

    return {
        "error": None,
        "total_return": round(total_return, 4),
        "sharpe_ratio": round(_calculate_sharpe(daily_returns), 2),
        "max_drawdown": round(_calculate_max_drawdown(equity_curve), 4),
        "win_rate": round(winning_trades / total_trades, 4) if total_trades > 0 else 0.0,
        "total_trades": total_trades,
        "equity_curve": equity_curve,
        "trade_log": trade_log,
    }
