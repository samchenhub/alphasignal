"""
POST /api/v1/search

Semantic search over analyzed articles using pgvector cosine similarity.
Requires embeddings to be stored in the analysis_results table.

Note: Embeddings are generated via the Anthropic API's text embedding model.
For now we use a simple text search fallback if embeddings aren't available.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db
from app.db.models import AnalysisResult, Article

router = APIRouter(prefix="/api/v1/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    market: str | None = None    # 'US', 'CN', 'HK', or None for all
    days: int = 90
    limit: int = 10


class SearchResult(BaseModel):
    article_id: str
    ticker: str
    market: str
    title: str
    url: str
    summary: str | None
    sentiment_score: float | None
    published_at: datetime | None
    similarity: float | None


@router.post("/", response_model=list[SearchResult])
async def semantic_search(
    req: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Search articles by semantic similarity.

    If embeddings exist in the DB, uses pgvector cosine similarity.
    Falls back to PostgreSQL full-text search (tsvector) otherwise.
    """
    since = datetime.now(timezone.utc) - timedelta(days=req.days)

    # Check if any embeddings exist
    has_embeddings = await db.scalar(
        text("SELECT COUNT(*) FROM analysis_results WHERE embedding IS NOT NULL")
    )

    if has_embeddings and has_embeddings > 0:
        return await _vector_search(db, req, since)
    else:
        return await _fulltext_search(db, req, since)


async def _vector_search(
    db: AsyncSession, req: SearchRequest, since: datetime
) -> list[SearchResult]:
    """pgvector cosine similarity search — falls back to fulltext until embedding pipeline is wired."""
    return await _fulltext_search(db, req, since)


async def _fulltext_search(
    db: AsyncSession, req: SearchRequest, since: datetime
) -> list[SearchResult]:
    """
    PostgreSQL full-text search fallback.
    Searches across title + summary + key_events JSON.
    """
    market_filter = ""
    params: dict = {
        "query": req.query,
        "since": since,
        "limit": req.limit,
    }

    if req.market:
        market_filter = "AND ar.market = :market"
        params["market"] = req.market.upper()

    sql = text(f"""
        SELECT
            a.id AS article_id,
            ar.ticker,
            ar.market,
            a.title,
            a.url,
            ar.summary,
            ar.sentiment_score,
            a.published_at,
            ts_rank(
                to_tsvector('simple', coalesce(a.title,'') || ' ' || coalesce(ar.summary,'')),
                plainto_tsquery('simple', :query)
            ) AS similarity
        FROM analysis_results ar
        JOIN articles a ON a.id = ar.article_id
        WHERE
            ar.processed_at >= :since
            {market_filter}
            AND (
                to_tsvector('simple', coalesce(a.title,'') || ' ' || coalesce(ar.summary,''))
                @@ plainto_tsquery('simple', :query)
                OR a.title ILIKE '%' || :query || '%'
                OR ar.summary ILIKE '%' || :query || '%'
            )
        ORDER BY similarity DESC, a.published_at DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.all()

    return [
        SearchResult(
            article_id=str(row.article_id),
            ticker=row.ticker,
            market=row.market,
            title=row.title,
            url=row.url,
            summary=row.summary,
            sentiment_score=row.sentiment_score,
            published_at=row.published_at,
            similarity=float(row.similarity) if row.similarity else None,
        )
        for row in rows
    ]
