"""
A-share and Hong Kong stock price fetcher via AKShare.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import StockPrice

logger = logging.getLogger(__name__)


async def sync_cn_prices(session: AsyncSession, days_back: int = 7) -> int:
    """
    Fetch recent daily price data for A-share tickers.
    AKShare uses code format like '600519' for Shanghai, '000858' for Shenzhen.
    """
    try:
        import akshare as ak
    except ImportError:
        logger.error("AKShare not installed")
        return 0

    tickers = settings.cn_ticker_list
    if not tickers:
        return 0

    start_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime(
        "%Y%m%d"
    )
    end_date = datetime.now(timezone.utc).strftime("%Y%m%d")
    rows_upserted = 0

    for ticker in tickers:
        def _fetch_sync(t=ticker):
            try:
                # 东方财富 A-share daily data
                df = ak.stock_zh_a_hist(
                    symbol=t,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="hfq",  # 后复权
                )
                return df
            except Exception as e:
                logger.warning("AKShare price fetch failed for %s: %s", t, e)
                return None

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(None, _fetch_sync)

        if df is None or df.empty:
            continue

        for _, row in df.iterrows():
            # Column names: 日期, 开盘, 收盘, 最高, 最低, 成交量, ...
            date_val = row.get("日期") or row.get("date")
            close_val = row.get("收盘") or row.get("close")
            volume_val = row.get("成交量") or row.get("volume")

            if date_val is None or close_val is None:
                continue

            if isinstance(date_val, str):
                ts = datetime.strptime(date_val, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
            else:
                ts = datetime.combine(date_val, datetime.min.time()).replace(
                    tzinfo=timezone.utc
                )

            stmt = (
                insert(StockPrice)
                .values(
                    ticker=ticker,
                    market="CN",
                    timestamp=ts,
                    close_price=float(close_val),
                    volume=int(volume_val) if volume_val else None,
                )
                .on_conflict_do_update(
                    constraint="uq_stock_prices_ticker_ts",
                    set_={
                        "close_price": float(close_val),
                        "volume": int(volume_val) if volume_val else None,
                    },
                )
            )
            await session.execute(stmt)
            rows_upserted += 1

    await session.commit()
    logger.info("Synced %d CN price rows", rows_upserted)
    return rows_upserted
