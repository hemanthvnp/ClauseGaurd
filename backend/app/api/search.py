"""
Cross-Document Semantic Search API
====================================
Search across ALL of a user's documents using FAISS-backed dense retrieval.

POST /search          — natural language query across the full document portfolio
GET  /search/suggest  — type-ahead category suggestions based on query prefix
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limiter import default_limiter
from app.core.security import get_current_user
from app.ml.vector_store import ClauseVectorStore, SearchResult
from app.models.schema import Clause, Document, User

router = APIRouter(prefix="/search", tags=["search"])


# ── Request / Response schemas ────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    top_k: int = Field(10, ge=1, le=50)
    risk_levels: list[str] = Field(
        default_factory=list,
        description="Filter results to specific risk levels: critical, high, medium, low",
    )
    document_ids: list[UUID] = Field(
        default_factory=list,
        description="Scope search to specific document IDs (empty = all documents)",
    )


class SearchHit(BaseModel):
    clause_id: str
    document_id: str
    document_filename: str
    category: str
    risk_level: str
    risk_score: float
    text: str
    plain_english: str
    score: float


class SearchResponse(BaseModel):
    query: str
    total_hits: int
    hits: list[SearchHit]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=SearchResponse)
def semantic_search(
    payload: SearchRequest,
    _: None = Depends(default_limiter),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    Performs semantic search across all processed documents owned by the user.

    Uses FAISS-based dense retrieval (all-MiniLM-L6-v2 embeddings) with
    BM25 sparse fusion for hybrid ranking.

    Results are filtered by risk level and/or document scope if provided.
    """
    # Load all complete documents belonging to the user
    doc_query = select(Document).where(
        Document.user_id == current_user.id,
        Document.status == "complete",
    )
    if payload.document_ids:
        doc_query = doc_query.where(Document.id.in_(payload.document_ids))
    docs = list(db.scalars(doc_query).all())

    if not docs:
        return SearchResponse(query=payload.query, total_hits=0, hits=[])

    doc_map = {str(d.id): d for d in docs}
    doc_ids = [d.id for d in docs]

    # Load clauses
    clauses = list(db.scalars(
        select(Clause).where(Clause.document_id.in_(doc_ids))
    ).all())

    if not clauses:
        return SearchResponse(query=payload.query, total_hits=0, hits=[])

    # Build ephemeral FAISS store (in production, cache this per-user with TTL)
    store = ClauseVectorStore.from_clauses(clauses)
    raw_results: list[SearchResult] = store.search(
        payload.query, top_k=payload.top_k * 3
    )

    # Filter by risk level
    allowed_levels = set(payload.risk_levels) if payload.risk_levels else None
    hits: list[SearchHit] = []
    for r in raw_results:
        if allowed_levels and r.risk_level not in allowed_levels:
            continue
        doc = doc_map.get(r.document_id)
        if doc is None:
            continue
        hits.append(SearchHit(
            clause_id=r.clause_id,
            document_id=r.document_id,
            document_filename=doc.filename,
            category=r.category,
            risk_level=r.risk_level,
            risk_score=r.risk_score,
            text=r.text[:500],
            plain_english=r.plain_english,
            score=r.score,
        ))
        if len(hits) >= payload.top_k:
            break

    return SearchResponse(query=payload.query, total_hits=len(hits), hits=hits)


@router.get("/suggest")
def suggest_categories(
    q: str = Query(..., min_length=1, max_length=100),
    _: None = Depends(default_limiter),
    current_user: User = Depends(get_current_user),
) -> list[str]:
    """
    Returns clause category suggestions that start with (or contain) the prefix.
    Used for search type-ahead UI.
    """
    from app.ml.clause_classifier import CLAUSE_LABELS
    lower_q = q.lower()
    return [
        label for label in CLAUSE_LABELS
        if lower_q in label.lower()
    ][:8]
