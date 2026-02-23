"""
Core LLM analysis pipeline using the Anthropic Claude API.

Two-stage processing:
  Stage 1 — Haiku (cheap, fast): filter irrelevant articles
  Stage 2 — Sonnet (powerful): full structured extraction

For each relevant article, produces:
  - sentiment_score (-1.0 to 1.0)
  - confidence (0.0 to 1.0)
  - named entities (companies, tickers, people)
  - one-sentence summary
  - key financial events
  - embedding vector (via Claude's text-embedding via Sonnet output reuse)
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.analysis.prompts import (
    ANALYSIS_SYSTEM,
    FILTER_SYSTEM,
    analysis_prompt,
    filter_prompt,
)
from app.config import settings
from app.db.models import Alert, AnalysisResult, Article

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_haiku(messages: list[dict], system: str) -> str:
    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=256,
        system=system,
        messages=messages,
    )
    return response.content[0].text


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_sonnet(messages: list[dict], system: str) -> str:
    response = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return response.content[0].text


def _is_relevant(title: str, content: str, tickers: list[str]) -> bool:
    """Stage 1: Quick relevance filter via Haiku."""
    prompt = filter_prompt(title, content, tickers)
    try:
        raw = _call_haiku([{"role": "user", "content": prompt}], FILTER_SYSTEM)
        data = json.loads(raw)
        return bool(data.get("relevant", False))
    except (json.JSONDecodeError, Exception) as e:
        logger.debug("Filter parse error: %s — defaulting to relevant", e)
        return True  # When in doubt, analyze it


def _analyze(title: str, content: str, tickers: list[str], market: str) -> dict | None:
    """Stage 2: Full structured extraction via Sonnet."""
    prompt = analysis_prompt(title, content, tickers, market)
    try:
        raw = _call_sonnet([{"role": "user", "content": prompt}], ANALYSIS_SYSTEM)
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[:-1])
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as e:
        logger.warning("JSON parse error in analysis: %s\nRaw: %s", e, raw[:200])
        return None
    except Exception as e:
        logger.error("Analysis API error: %s", e)
        return None


async def process_unanalyzed_articles(
    session: AsyncSession,
    batch_size: int = 20,
) -> int:
    """
    Main processing loop: fetch unprocessed articles, run analysis, store results.
    Returns the number of articles processed.
    """
    if client is None:
        logger.warning("ANTHROPIC_API_KEY not set — skipping LLM analysis")
        return 0

    tickers_us = settings.us_ticker_list
    tickers_cn = settings.cn_ticker_list

    # Fetch unprocessed articles
    result = await session.execute(
        select(Article)
        .where(Article.is_processed == False)  # noqa: E712
        .order_by(Article.fetched_at.desc())
        .limit(batch_size)
    )
    articles: list[Article] = list(result.scalars().all())

    if not articles:
        return 0

    processed_count = 0

    for article in articles:
        tickers = tickers_us if article.market == "US" else tickers_cn

        # Stage 1: Filter (run sync function in thread pool to avoid blocking event loop)
        relevant = await asyncio.to_thread(
            _is_relevant,
            article.title or "",
            article.content or "",
            tickers,
        )

        if not relevant:
            article.is_processed = True
            continue

        # Stage 2: Deep analysis (run sync function in thread pool)
        result_data = await asyncio.to_thread(
            _analyze,
            article.title or "",
            article.content or "",
            tickers,
            article.market,
        )

        article.is_processed = True

        if not result_data:
            continue

        relevant_tickers = result_data.get("relevant_tickers", [])
        if not relevant_tickers:
            continue

        # Create one AnalysisResult per relevant ticker
        for ticker in relevant_tickers:
            analysis = AnalysisResult(
                article_id=article.id,
                ticker=ticker,
                market=article.market,
                sentiment_score=result_data.get("sentiment_score"),
                confidence=result_data.get("confidence"),
                entities=result_data.get("entities"),
                summary=result_data.get("summary"),
                key_events=result_data.get("key_events"),
                model_version=SONNET_MODEL,
            )
            session.add(analysis)

            # Check alert thresholds
            score = result_data.get("sentiment_score", 0.0) or 0.0
            confidence = result_data.get("confidence", 0.0) or 0.0

            if (
                abs(score) >= settings.alert_sentiment_threshold
                and confidence >= settings.alert_confidence_threshold
            ):
                alert_type = "extreme_positive" if score > 0 else "extreme_negative"
                direction = "BULLISH" if score > 0 else "BEARISH"
                alert = Alert(
                    article_id=article.id,
                    ticker=ticker,
                    alert_type=alert_type,
                    message=(
                        f"[{direction}] {ticker}: score={score:.2f}, "
                        f"confidence={confidence:.2f} — {result_data.get('summary', '')}"
                    ),
                    is_sent=False,
                )
                session.add(alert)
                logger.warning(
                    "ALERT triggered for %s: %s (score=%.2f)", ticker, alert_type, score
                )

        processed_count += 1

    await session.commit()
    logger.info("Processed %d articles", processed_count)
    return processed_count
