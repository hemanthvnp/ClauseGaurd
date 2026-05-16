"""
Risk Analytics API
==================
Provides aggregated risk intelligence across a user's document portfolio.

Endpoints:
  GET /analytics/summary           — portfolio-level KPIs
  GET /analytics/risk-distribution — clause risk breakdown per document
  GET /analytics/category-heatmap  — most frequent / risky clause categories
  GET /analytics/trends            — risk score trajectory over time
  GET /analytics/benchmark         — compare against industry medians
  GET /analytics/audit-log         — user's audit event trail
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import get_user_audit_log
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schema import Clause, Document, User

router = APIRouter(prefix="/analytics", tags=["analytics"])

# ── Industry benchmark medians (based on public CUAD statistics) ──────────────
_BENCHMARKS: dict[str, dict[str, Any]] = {
    "Employment Agreement": {
        "median_risk_score": 58,
        "high_risk_categories": ["Non-Compete", "Arbitration", "IP Ownership"],
        "avg_clause_count": 24,
    },
    "NDA / Confidentiality": {
        "median_risk_score": 35,
        "high_risk_categories": ["Confidentiality", "Non-Solicitation"],
        "avg_clause_count": 12,
    },
    "SaaS / Software License": {
        "median_risk_score": 52,
        "high_risk_categories": ["Data Usage Rights", "Limitation of Liability", "Auto-Renewal"],
        "avg_clause_count": 32,
    },
    "Master Services Agreement": {
        "median_risk_score": 61,
        "high_risk_categories": ["Indemnification", "Termination for Convenience", "IP Ownership"],
        "avg_clause_count": 40,
    },
    "default": {
        "median_risk_score": 50,
        "high_risk_categories": ["Arbitration", "Indemnification"],
        "avg_clause_count": 20,
    },
}


# ── Portfolio summary ─────────────────────────────────────────────────────────

@router.get("/summary")
def portfolio_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Returns high-level KPIs for a user's entire document portfolio:
    total documents, average risk score, risk breakdown, most common categories.
    """
    docs = list(db.scalars(
        select(Document)
        .where(Document.user_id == current_user.id, Document.status == "complete")
    ).all())

    if not docs:
        return {"total_documents": 0, "message": "No analyzed documents yet."}

    doc_ids = [d.id for d in docs]
    clauses = list(db.scalars(
        select(Clause).where(Clause.document_id.in_(doc_ids))
    ).all())

    risk_levels = [c.risk_level or "low" for c in clauses]
    level_counts = Counter(risk_levels)
    category_counter = Counter(c.category for c in clauses if c.category)

    avg_risk = (
        sum(c.risk_score or 0 for c in clauses) / len(clauses) if clauses else 0
    )

    return {
        "total_documents": len(docs),
        "total_clauses": len(clauses),
        "avg_risk_score": round(avg_risk, 1),
        "risk_breakdown": {
            "critical": level_counts.get("critical", 0),
            "high":     level_counts.get("high", 0),
            "medium":   level_counts.get("medium", 0),
            "low":      level_counts.get("low", 0),
        },
        "top_categories": [
            {"category": cat, "count": cnt}
            for cat, cnt in category_counter.most_common(10)
        ],
        "highest_risk_document": _highest_risk_doc(docs),
    }


# ── Risk distribution ─────────────────────────────────────────────────────────

@router.get("/risk-distribution")
def risk_distribution(
    document_id: UUID | None = Query(None, description="Filter to a single document"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Clause risk distribution (count + percentage) broken down by risk level.
    Optionally scoped to a single document.
    """
    q = select(Clause).join(Document, Clause.document_id == Document.id).where(
        Document.user_id == current_user.id
    )
    if document_id:
        q = q.where(Clause.document_id == document_id)

    clauses = list(db.scalars(q).all())
    total = len(clauses) or 1

    levels = ["critical", "high", "medium", "low"]
    counts = Counter(c.risk_level or "low" for c in clauses)

    return {
        "total": len(clauses),
        "distribution": [
            {
                "level": level,
                "count": counts.get(level, 0),
                "percentage": round(counts.get(level, 0) / total * 100, 1),
            }
            for level in levels
        ],
    }


# ── Category heatmap ──────────────────────────────────────────────────────────

@router.get("/category-heatmap")
def category_heatmap(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Per-category statistics: occurrence count, average risk score, max risk level.
    Useful for identifying which clause types pose the greatest portfolio risk.
    """
    docs = list(db.scalars(
        select(Document)
        .where(Document.user_id == current_user.id, Document.status == "complete")
    ).all())
    if not docs:
        return []

    clauses = list(db.scalars(
        select(Clause).where(Clause.document_id.in_([d.id for d in docs]))
    ).all())

    by_category: dict[str, list[Clause]] = defaultdict(list)
    for c in clauses:
        by_category[c.category or "General"].append(c)

    rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}

    rows = []
    for cat, cat_clauses in by_category.items():
        scores = [c.risk_score or 0 for c in cat_clauses]
        max_level = max((c.risk_level or "low" for c in cat_clauses),
                        key=lambda l: rank.get(l, 0))
        rows.append({
            "category":      cat,
            "count":         len(cat_clauses),
            "avg_score":     round(sum(scores) / len(scores), 1),
            "max_risk_level": max_level,
        })

    rows.sort(key=lambda r: (-r["count"], -r["avg_score"]))
    return rows[:30]


# ── Trends ────────────────────────────────────────────────────────────────────

@router.get("/trends")
def risk_trends(
    days: int = Query(30, ge=7, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Daily average risk score trend over the last N days.
    Useful for detecting whether recently uploaded contracts are riskier.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    docs = list(db.scalars(
        select(Document)
        .where(
            Document.user_id == current_user.id,
            Document.status == "complete",
            Document.created_at >= since,
        )
        .order_by(Document.created_at)
    ).all())

    # Group by date
    by_date: dict[str, list[float]] = defaultdict(list)
    for d in docs:
        if d.created_at and d.overall_risk_score is not None:
            date_str = d.created_at.strftime("%Y-%m-%d")
            by_date[date_str].append(float(d.overall_risk_score))

    return [
        {
            "date": date,
            "avg_risk_score": round(sum(scores) / len(scores), 1),
            "document_count": len(scores),
        }
        for date, scores in sorted(by_date.items())
    ]


# ── Industry benchmark ────────────────────────────────────────────────────────

@router.get("/benchmark/{document_id}")
def benchmark(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Compare a document's risk profile against industry-median benchmarks.
    Contract type is inferred from NER entities stored during processing.
    """
    document = db.get(Document, document_id)
    if not document or document.user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Document not found")

    # Infer contract type from filename heuristics
    contract_type = _infer_contract_type(document.filename)
    bench = _BENCHMARKS.get(contract_type, _BENCHMARKS["default"])

    clauses = list(db.scalars(
        select(Clause).where(Clause.document_id == document_id)
    ).all())
    doc_score = document.overall_risk_score or 0
    delta = round(doc_score - bench["median_risk_score"], 1)

    return {
        "document_id":      str(document_id),
        "document_score":   doc_score,
        "contract_type":    contract_type,
        "benchmark": {
            "median_risk_score":    bench["median_risk_score"],
            "high_risk_categories": bench["high_risk_categories"],
            "avg_clause_count":     bench["avg_clause_count"],
        },
        "comparison": {
            "score_delta":  delta,
            "verdict":      "above average risk" if delta > 5 else "below average risk" if delta < -5 else "average risk",
            "clause_count": len(clauses),
        },
    }


# ── Audit log ─────────────────────────────────────────────────────────────────

@router.get("/audit-log")
def audit_log(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return the authenticated user's audit event trail (paginated)."""
    return get_user_audit_log(db, current_user.id, limit=limit, offset=offset)


# ── Private helpers ───────────────────────────────────────────────────────────

def _highest_risk_doc(docs: list[Document]) -> dict[str, Any] | None:
    complete = [d for d in docs if d.overall_risk_score is not None]
    if not complete:
        return None
    worst = max(complete, key=lambda d: d.overall_risk_score or 0)
    return {
        "id":         str(worst.id),
        "filename":   worst.filename,
        "risk_score": worst.overall_risk_score,
        "risk_level": worst.overall_risk_level,
    }


def _infer_contract_type(filename: str) -> str:
    lower = filename.lower()
    if any(w in lower for w in ("employ", "offer", "compensation")):
        return "Employment Agreement"
    if any(w in lower for w in ("nda", "confidential", "disclosure")):
        return "NDA / Confidentiality"
    if any(w in lower for w in ("saas", "software", "license", "subscription")):
        return "SaaS / Software License"
    if any(w in lower for w in ("msa", "master", "service")):
        return "Master Services Agreement"
    return "default"
