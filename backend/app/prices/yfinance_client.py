"""
US stock price fetcher using yfinance.

Fetches daily OHLCV data and stores it aligned with article timestamps.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import StockPrice

logger = logging.getLogger(__name__)


async def sync_us_prices(session: AsyncSession, days_back: int = 7) -> int:
    """
    Fetch recent price data for all tracked US tickers.
    Uses upsert to avoid duplicates.
    Returns number of rows inserted/updated.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed")
        return 0

    tickers = settings.us_ticker_list
    if not tickers:
        return 0

    start = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime(
        "%Y-%m-%d"
    )

    def _fetch_sync():
        data = yf.download(
            tickers,
            start=start,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        return data

    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, _fetch_sync)

    if data.empty:
        logger.warning("yfinance returned empty data for US tickers")
        return 0

    rows_upserted = 0

    # Handle single ticker (flat DataFrame) vs multi-ticker (MultiIndex columns)
    if len(tickers) == 1:
        ticker = tickers[0]
        for ts, row in data.iterrows():
            close = float(row["Close"]) if "Close" in row else None
            volume = int(row["Volume"]) if "Volume" in row else None
            if close is None:
                continue
            stmt = (
                insert(StockPrice)
                .values(
                    ticker=ticker,
                    market="US",
                    timestamp=ts.to_pydatetime().replace(tzinfo=timezone.utc),
                    close_price=close,
                    volume=volume,
                )
                .on_conflict_do_update(
                    constraint="uq_stock_prices_ticker_ts",
                    set_={"close_price": close, "volume": volume},
                )
            )
            await session.execute(stmt)
            rows_upserted += 1
    else:
        # Multi-ticker: yfinance returns MultiIndex columns (field, ticker)
        # data["Close"] yields a DataFrame with ticker names as columns
        try:
            close_df = data["Close"]
            volume_df = data["Volume"] if "Volume" in data.columns.get_level_values(0) else None
        except Exception as e:
            logger.warning("yfinance MultiIndex access failed: %s", e)
            return 0

        for ticker in tickers:
            if ticker not in close_df.columns:
                logger.debug("Ticker %s not in yfinance response, skipping", ticker)
                continue
            try:
                close_series = close_df[ticker]
                volume_series = volume_df[ticker] if volume_df is not None else None

                for ts, close in close_series.items():
                    if close != close:  # NaN check
                        continue
                    volume = None
                    if volume_series is not None:
                        v = volume_series[ts]
                        volume = int(v) if v == v else None  # NaN-safe
                    stmt = (
                        insert(StockPrice)
                        .values(
                            ticker=ticker,
                            market="US",
                            timestamp=ts.to_pydatetime().replace(tzinfo=timezone.utc),
                            close_price=float(close),
                            volume=volume,
                        )
                        .on_conflict_do_update(
                            constraint="uq_stock_prices_ticker_ts",
                            set_={"close_price": float(close), "volume": volume},
                        )
                    )
                    await session.execute(stmt)
                    rows_upserted += 1
            except Exception as e:
                logger.warning("Failed to process prices for %s: %s", ticker, e)

    await session.commit()
    logger.info("Synced %d US price rows", rows_upserted)
    return rows_upserted
