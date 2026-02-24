"""
Structured prompt templates for Claude API.

Two-stage design:
  1. Haiku (fast/cheap): Filter — is this article relevant to any tracked ticker?
  2. Sonnet (powerful): Analyze — extract full structured features.
"""

FILTER_SYSTEM = """You are a financial news classifier. Given a news article, determine if it contains meaningful information about specific publicly traded companies, stock markets, or financial events that could affect stock prices.

Respond with valid JSON only:
{"relevant": true, "reason": "brief reason"}
or
{"relevant": false, "reason": "brief reason"}"""


# Map ticker symbols to company names for better LLM matching
_TICKER_NAMES = {
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Google/Alphabet",
    "AMZN": "Amazon", "NVDA": "Nvidia", "TSLA": "Tesla", "META": "Meta/Facebook",
    "JPM": "JPMorgan Chase", "V": "Visa", "JNJ": "Johnson & Johnson",
    "WMT": "Walmart", "XOM": "ExxonMobil", "BAC": "Bank of America",
    "MA": "Mastercard", "PG": "Procter & Gamble", "HD": "Home Depot",
    "CVX": "Chevron", "MRK": "Merck", "ABBV": "AbbVie", "PFE": "Pfizer",
    "KO": "Coca-Cola", "AVGO": "Broadcom", "COST": "Costco",
    "TMO": "Thermo Fisher", "CSCO": "Cisco", "MCD": "McDonald's",
    "DIS": "Disney", "ADBE": "Adobe", "CRM": "Salesforce", "NFLX": "Netflix",
    "AMD": "AMD", "INTC": "Intel", "QCOM": "Qualcomm",
    "GS": "Goldman Sachs", "MS": "Morgan Stanley",
}


def filter_prompt(title: str, content: str, tickers: list[str]) -> str:
    # Include company names so the LLM can match "Home Depot" → HD, etc.
    ticker_with_names = ", ".join(
        f"{t} ({_TICKER_NAMES[t]})" if t in _TICKER_NAMES else t
        for t in tickers
    )
    snippet = (content or "")[:800]
    return f"""Tracked tickers (ticker: company name): {ticker_with_names}

Article title: {title}

Article snippet: {snippet}

Is this article relevant to any of the tracked companies/tickers, or to major market events affecting them? Respond with JSON."""


# ─────────────────────────────────────────────
# Deep analysis prompt (Sonnet)
# ─────────────────────────────────────────────

ANALYSIS_SYSTEM = """You are a senior financial analyst AI. Analyze news articles and extract structured financial intelligence.

You MUST respond with valid JSON matching this exact schema:
{
  "relevant_tickers": ["AAPL", "MSFT"],
  "sentiment_score": 0.0,
  "confidence": 0.0,
  "entities": {
    "companies": ["Apple Inc."],
    "tickers": ["AAPL"],
    "people": ["Tim Cook"]
  },
  "summary": "One precise sentence summarizing the core financial event.",
  "key_events": [
    {"type": "event_type", "description": "description"}
  ]
}

Rules:
- sentiment_score: float from -1.0 (extremely bearish) to 1.0 (extremely bullish). 0.0 = neutral.
- confidence: float from 0.0 to 1.0 reflecting your certainty in the sentiment assessment.
- relevant_tickers: only tickers from the provided watchlist that this article meaningfully covers.
- key_events type must be one of: earnings_beat, earnings_miss, earnings_warning, revenue_guidance_up, revenue_guidance_down, merger_acquisition, product_launch, regulatory_action, executive_change, debt_restructuring, dividend_change, share_buyback, analyst_upgrade, analyst_downgrade, macro_event, other.
- summary: maximum 2 sentences, in the same language as the article. Focus on the financial impact.
- If the article is not relevant to any tracked ticker, return relevant_tickers as an empty list."""


def analysis_prompt(title: str, content: str, tickers: list[str], market: str) -> str:
    ticker_list = ", ".join(tickers)
    market_label = "US equity markets" if market == "US" else "中国A股/港股市场"
    # Limit content to avoid token overflow while keeping substance
    full_text = f"{title}\n\n{content or ''}"
    truncated = full_text[:3000]

    return f"""Market context: {market_label}
Watchlist tickers: {ticker_list}

Article to analyze:
---
{truncated}
---

Analyze this article and return structured JSON."""
