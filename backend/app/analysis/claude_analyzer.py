"""
LLM Analysis Pipeline — Groq + Llama 3.3 70B

Two-stage processing:
  Stage 1 — Llama 3.3 70B (fast): filter irrelevant articles
  Stage 2 — Llama 3.3 70B (powerful): full structured extraction

Free tier: 14,400 requests/day, 30 RPM
https://console.groq.com
"""
import asyncio
import json
import logging

from groq import Groq
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

GROQ_MODEL = "llama-3.3-70b-versatile"

# Initialise Groq client — None when API key is not configured
_client = None
if settings.groq_api_key:
    _client = Groq(api_key=settings.groq_api_key)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_groq_filter(prompt: str) -> str:
    response = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": FILTER_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        max_tokens=256,
        temperature=0.1,
    )
    return response.choices[0].message.content


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_groq_analysis(prompt: str) -> str:
    response = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": ANALYSIS_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    return response.choices[0].message.content


def _strip_fences(raw: str) -> str:
    """Remove markdown code fences that LLMs sometimes wrap JSON in."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
    if cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[:-1])
    return cleaned.strip()


def _is_relevant(title: str, content: str, tickers: list[str]) -> bool:
    """Stage 1: Quick relevance filter."""
    prompt = filter_prompt(title, content, tickers)
    try:
        raw = _call_groq_filter(prompt)
        data = json.loads(_strip_fences(raw))
        return bool(data.get("relevant", False))
    except Exception as e:
        logger.debug("Filter parse error: %s — defaulting to relevant", e)
        return True


def _analyze(title: str, content: str, tickers: list[str], market: str) -> dict | None:
    """Stage 2: Full structured extraction."""
    prompt = analysis_prompt(title, content, tickers, market)
    raw = ""
    try:
        raw = _call_groq_analysis(prompt)
        return json.loads(_strip_fences(raw))
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
    if _client is None:
        logger.warning("GROQ_API_KEY not set — skipping LLM analysis")
        return 0

    tickers_us = settings.us_ticker_list
    tickers_cn = settings.cn_ticker_list

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

        relevant = await asyncio.to_thread(
            _is_relevant,
            article.title or "",
            article.content or "",
            tickers,
        )

        if not relevant:
            article.is_processed = True
            continue

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
                model_version=GROQ_MODEL,
            )
            session.add(analysis)

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
