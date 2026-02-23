# AlphaSignal

A real-time financial intelligence platform that monitors US, A-share, and Hong Kong market news, extracts structured sentiment signals using Claude AI, and visualizes them alongside stock prices.

> **Status:** Core infrastructure complete and running. LLM analysis requires an Anthropic API key — the platform runs without one, skipping the analysis step.

---

## What It Does

Every 15 minutes, AlphaSignal automatically:

1. **Fetches news** from NYT Business, Seeking Alpha, MarketWatch, SEC EDGAR, and Chinese market sources (东方财富 via AKShare)
2. **Filters articles** using Claude Haiku — quickly discards anything unrelated to tracked tickers
3. **Analyzes relevant articles** using Claude Sonnet — extracts sentiment score, confidence, named entities, and key financial events
4. **Syncs stock prices** (US via yfinance, CN/HK via AKShare) every hour
5. **Triggers alerts** when sentiment exceeds extreme thresholds (|score| > 0.85, confidence > 0.90)

Results are exposed via a REST API and visualized in a Next.js dashboard.

---

## Architecture

```
News Sources                  Processing                    Storage
────────────                  ──────────                    ───────
NYT Business RSS  ──┐
Seeking Alpha RSS ──┤         Stage 1: Claude Haiku        PostgreSQL
MarketWatch RSS   ──┼──────►  (relevance filter)   ──────► + pgvector
SEC EDGAR (8-K)   ──┤              │
AKShare (CN/HK)   ──┘         Stage 2: Claude Sonnet            │
                              (structured extraction)            │
yfinance / AKShare ──────────────────────────────────────────────┤
(price data, hourly)                                             │
                                                                 ▼
                                                    FastAPI REST API
                                                         │
                                                    Next.js Dashboard
```

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Alembic |
| AI | Anthropic Claude API (Haiku + Sonnet) |
| Database | PostgreSQL 16 + pgvector |
| Data | yfinance (US prices), AKShare (CN/HK prices + news) |
| Scheduling | APScheduler 3.10 |
| Frontend | Next.js 14, Recharts, TailwindCSS, SWR |
| Infrastructure | Docker Compose |

---

## Quick Start

**Requirements:** Docker Desktop

```bash
git clone https://github.com/yourname/alphasignal.git
cd alphasignal
cp .env.example .env
# Optional: add your ANTHROPIC_API_KEY to .env for LLM analysis
docker compose up --build
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |

On first startup, AlphaSignal immediately fetches news and syncs 90 days of price history. Data appears in the dashboard within ~2 minutes.

**To change which stocks you track**, edit `US_TICKERS` and `CN_TICKERS` in `.env` and restart.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/sentiment/{ticker}` | Sentiment time series (default: last 7 days) |
| `GET` | `/api/v1/sentiment/{ticker}/price-correlation` | Daily avg sentiment + price for chart |
| `GET` | `/api/v1/news/{ticker}` | Analyzed news for a specific ticker |
| `GET` | `/api/v1/news/` | Latest news across all tracked tickers |
| `POST` | `/api/v1/search/` | Full-text search across analyzed articles |
| `GET` | `/api/v1/alerts/` | Extreme sentiment event alerts |
| `GET` | `/health` | Health check |

**Examples:**

```bash
# Get AAPL price + sentiment data for the last 30 days
curl "http://localhost:8000/api/v1/sentiment/AAPL/price-correlation?days=30"

# Search for articles about supply chain issues
curl -X POST http://localhost:8000/api/v1/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "supply chain disruption", "market": "US", "days": 90}'
```

---

## LLM Analysis Pipeline

When an Anthropic API key is configured, each relevant article is processed through a two-stage pipeline:

**Stage 1 — Claude Haiku (fast, cheap):** Determines whether the article mentions any tracked ticker. Irrelevant articles are skipped immediately.

**Stage 2 — Claude Sonnet (structured extraction):** Produces a structured JSON output:

```json
{
  "relevant_tickers": ["AAPL"],
  "sentiment_score": -0.82,
  "confidence": 0.91,
  "entities": {
    "companies": ["Apple Inc."],
    "tickers": ["AAPL"],
    "people": ["Tim Cook"]
  },
  "summary": "Apple cut Q4 revenue guidance citing supply chain disruptions.",
  "key_events": [
    {"type": "revenue_guidance_down", "description": "Q4 guidance cut by 8%"}
  ]
}
```

This two-stage design keeps API costs low — only articles that pass the Haiku filter consume Sonnet tokens.

---

## Data Sources

| Market | News Sources | Price Data |
|--------|-------------|------------|
| US | NYT Business, Seeking Alpha, MarketWatch, SEC EDGAR (8-K filings) | yfinance |
| A-Share | 东方财富 via AKShare | AKShare |
| HK | 东方财富港股 via AKShare | AKShare |

---

## Project Structure

```
alphasignal/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI app, startup/shutdown
│       ├── config.py            # Settings from .env
│       ├── ingestion/
│       │   ├── rss_fetcher.py   # US RSS feeds (NYT, Seeking Alpha, MarketWatch)
│       │   ├── akshare_news.py  # CN/HK news via AKShare
│       │   └── sec_edgar.py     # SEC 8-K filings
│       ├── analysis/
│       │   ├── claude_analyzer.py  # Two-stage LLM pipeline
│       │   └── prompts.py          # System prompts
│       ├── prices/
│       │   ├── yfinance_client.py  # US price sync
│       │   └── akshare_prices.py   # CN/HK price sync
│       ├── scheduler/
│       │   └── tasks.py         # APScheduler job definitions
│       ├── api/
│       │   ├── sentiment.py     # /api/v1/sentiment/*
│       │   ├── news.py          # /api/v1/news/*
│       │   ├── search.py        # /api/v1/search/
│       │   └── alerts.py        # /api/v1/alerts/
│       └── db/
│           ├── models.py        # SQLAlchemy ORM models
│           ├── connection.py    # Async session factory
│           └── migrations/      # Alembic migrations
├── frontend/
│   └── src/app/
│       ├── page.tsx             # Main dashboard
│       └── components/
│           ├── StockChart.tsx   # Price + sentiment composed chart
│           ├── NewsFeed.tsx     # Article list with sentiment badges
│           ├── AlertsPanel.tsx  # Extreme sentiment events
│           └── SearchPanel.tsx  # Article search UI
├── docker-compose.yml
└── .env.example
```

---

## Configuration

All settings are in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(empty)* | Claude API key — LLM analysis skipped if not set |
| `US_TICKERS` | `AAPL,MSFT,GOOGL,AMZN,NVDA,TSLA,META` | US stocks to track |
| `CN_TICKERS` | `600519,000858,300750` | A-share tickers (Moutai, Wuliangye, CATL) |
| `FETCH_INTERVAL_MINUTES` | `15` | How often to fetch news |
| `ALERT_SENTIMENT_THRESHOLD` | `0.85` | Sentiment score threshold for alerts |
| `ALERT_WEBHOOK_URL` | *(empty)* | Slack/custom webhook for alert notifications |
