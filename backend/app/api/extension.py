from __future__ import annotations

import time
from collections import Counter
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, status

from app.models.schema import AnalyzeTextClause, AnalyzeTextRequest, AnalyzeTextResponse
from app.ml.claude_explainer import get_claude_explainer
from app.ml.clause_classifier import get_classifier
from app.ml.clause_segmenter import ClauseSegmenter
from app.ml.risk_scorer import risk_scorer

router = APIRouter(prefix='/extension', tags=['extension'])
segmenter = ClauseSegmenter()
classifier = get_classifier()
explainer = get_claude_explainer()

# Simple in-memory rate limiter: 10 requests per IP per 60 seconds
_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW = 60.0
_rate_buckets: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW
    timestamps = _rate_buckets[client_ip]
    _rate_buckets[client_ip] = [t for t in timestamps if t > cutoff]
    if len(_rate_buckets[client_ip]) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail='Rate limit exceeded. Please wait before analyzing again.',
            headers={'Retry-After': str(int(_RATE_LIMIT_WINDOW))},
        )
    _rate_buckets[client_ip].append(now)


@router.post('/analyze-text', response_model=AnalyzeTextResponse)
def analyze_text(payload: AnalyzeTextRequest, request: Request) -> AnalyzeTextResponse:
    client_ip = request.client.host if request.client else '0.0.0.0'
    _check_rate_limit(client_ip)

    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Text must not be empty.')

    segments = segmenter.segment(payload.text)
    clauses: list[AnalyzeTextClause] = []
    risk_scores: list[float] = []
    risk_levels: list[str] = []

    for segment in segments:
        classification = classifier.classify(segment.text)
        assessment = risk_scorer.score(classification.category, segment.text, classification.confidence)
        explanation = explainer.explain(classification.category, assessment.risk_level, segment.text)
        clauses.append(
            AnalyzeTextClause(
                text=segment.text,
                category=classification.category,
                risk_level=assessment.risk_level,
                risk_score=assessment.risk_score,
                is_standard=assessment.is_standard,
                percentile=assessment.percentile,
                explanation=explanation,
            )
        )
        risk_scores.append(assessment.risk_score)
        risk_levels.append(assessment.risk_level)

    summary = Counter(risk_levels)
    overall_score = round(sum(risk_scores) / max(len(risk_scores), 1), 2)
    rank = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
    overall_level = max(summary, key=lambda level: rank.get(level, 0), default='low')
    return AnalyzeTextResponse(
        summary=dict(summary),
        clauses=clauses,
        overall_risk_score=overall_score,
        overall_risk_level=overall_level,
    )
