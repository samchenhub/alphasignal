"""
LLM Analysis Pipeline — Google Gemini 2.0 Flash

Two-stage processing:
  Stage 1 — Gemini Flash (fast): filter irrelevant articles
  Stage 2 — Gemini Flash (powerful): full structured extraction

Free tier: 1,500 requests/day, 1M tokens/day
https://aistudio.google.com
"""
import asyncio
import json
import logging

from google import genai
from google.genai import types
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

GEMINI_MODEL = "gemini-2.0-flash"

# Initialise Gemini client — None when API key is not configured
_client = None
if settings.gemini_api_key:
    _client = genai.Client(api_key=settings.gemini_api_key)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_gemini_filter(prompt: str) -> str:
    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=FILTER_SYSTEM,
            max_output_tokens=256,
        ),
    )
    return response.text


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_gemini_analysis(prompt: str) -> str:
    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=ANALYSIS_SYSTEM,
            max_output_tokens=1024,
        ),
    )
    return response.text


def _strip_fences(raw: str) -> str:
    """Remove markdown code fences that Gemini sometimes wraps JSON in."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
    if cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[:-1])
    return cleaned.strip()


def _is_relevant(title: str, content: str, tickers: list[str]) -> bool:
    """Stage 1: Quick relevance filter via Gemini Flash."""
    prompt = filter_prompt(title, content, tickers)
    try:
        raw = _call_gemini_filter(prompt)
        data = json.loads(_strip_fences(raw))
        return bool(data.get("relevant", False))
    except Exception as e:
        logger.debug("Filter parse error: %s — defaulting to relevant", e)
        return True  # When in doubt, analyse it


def _analyze(title: str, content: str, tickers: list[str], market: str) -> dict | None:
    """Stage 2: Full structured extraction via Gemini Flash."""
    prompt = analysis_prompt(title, content, tickers, market)
    raw = ""
    try:
        raw = _call_gemini_analysis(prompt)
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
        logger.warning("GEMINI_API_KEY not set — skipping LLM analysis")
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
                model_version=GEMINI_MODEL,
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
