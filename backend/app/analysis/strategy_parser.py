"""
Natural Language → Structured Strategy Parser

Uses Groq llama-3.3-70b to convert a plain-English trading strategy description
into a structured JSON representation that the backtest engine can execute.

Example input:  "When NVDA sentiment drops below -0.7, short the stock. Cover after 5 days."
Example output: {
    "ticker": "NVDA",
    "direction": "short",
    "entry": {"metric": "sentiment_score", "operator": "<", "threshold": -0.7},
    "exit": {"type": "time_based", "holding_days": 5}
}
"""
import asyncio
import json
import logging

from groq import Groq

from app.config import settings

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"

_client = None
if settings.groq_api_key:
    _client = Groq(api_key=settings.groq_api_key)

SYSTEM_PROMPT = """You are a financial strategy parser. Convert natural language trading strategies into structured JSON.

The strategy must be based on sentiment scores (ranging from -1.0 to 1.0, where negative = bearish, positive = bullish).

Output ONLY valid JSON with this exact schema:
{
  "ticker": "TICKER_SYMBOL",
  "direction": "long" | "short",
  "entry": {
    "metric": "sentiment_score",
    "operator": "<" | ">" | "<=" | ">=",
    "threshold": <float between -1.0 and 1.0>
  },
  "exit": {
    "type": "time_based",
    "holding_days": <integer 1-30>
  },
  "error": null
}

If you cannot parse a valid strategy, return:
{"error": "Brief explanation of what is missing or unclear"}

Rules:
- ticker: extract the stock ticker symbol (e.g., AAPL, NVDA, AMZN). If not mentioned, use the one provided separately.
- direction: "long" if buying/going long/bullish entry; "short" if shorting/selling/bearish entry
- entry.threshold: the sentiment score trigger. Typical values: extreme bearish = -0.7, extreme bullish = 0.7
- exit.holding_days: how many trading days to hold the position (default 5 if not specified)
- Do NOT include markdown fences or explanations — just the JSON object.
"""


def _parse_strategy_sync(natural_language: str, ticker_hint: str) -> dict:
    """Synchronous Groq call — run via asyncio.to_thread."""
    if _client is None:
        return {"error": "LLM service not configured (GROQ_API_KEY missing)"}

    user_prompt = f"""Parse this trading strategy into JSON.
Default ticker if not mentioned in the strategy: {ticker_hint}

Strategy: {natural_language}"""

    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=512,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1])
        raw = raw.strip()

        parsed = json.loads(raw)
        return parsed

    except json.JSONDecodeError as e:
        logger.warning("Strategy parser JSON decode error: %s", e)
        return {"error": "Could not parse LLM response as JSON. Please rephrase your strategy."}
    except Exception as e:
        err_str = str(e)
        if "rate_limit" in err_str or "429" in err_str:
            if "tokens per day" in err_str or "TPD" in err_str:
                return {"error": "Daily AI quota exhausted. Resets at midnight PST — please try again tomorrow."}
            return {"error": "AI service is busy (rate limit). Please wait a minute and try again."}
        logger.error("Strategy parser error: %s", e)
        return {"error": f"Parser error: {str(e)}"}


async def parse_strategy(natural_language: str, ticker_hint: str) -> dict:
    """
    Parse a natural language trading strategy asynchronously.

    Returns a dict with either the parsed strategy fields or an "error" key.
    """
    return await asyncio.to_thread(_parse_strategy_sync, natural_language, ticker_hint)
