"""
ClauseGuard AI Chat — Advanced Pipeline
========================================
RAG:   HyDE (hypothetical embeddings) + multi-query expansion + semantic search
LLM:   Groq Llama 3.3 70B streaming (free)
UX:    Server-Sent Events streaming, follow-up questions, negotiation advice
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from uuid import UUID

try:
    import numpy as np
    _NUMPY_OK = True
except Exception:
    np = None  # type: ignore[assignment]
    _NUMPY_OK = False
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schema import Clause, ChatRequest, ChatResponse, Document, User

router = APIRouter(prefix='/chat', tags=['chat'])
settings = get_settings()

_GROQ_URL   = 'https://api.groq.com/openai/v1/chat/completions'
_GROQ_MODEL = 'llama-3.3-70b-versatile'

_SYSTEM = """\
You are ClauseGuard, an elite AI legal document analyst.

For EVERY response, use this structure:
**VERDICT**: Start with ✅ Safe / ⚠️ Review Needed / ❌ Risky — one clear sentence.
**EVIDENCE**: List the specific clauses (name + risk score) that support your verdict.
**WHAT IT MEANS**: Plain-English explanation of the practical impact for the person signing.
**NEGOTIATE**: (only for risky/high clauses) Concrete suggestions — what to push back on, what language to request.
**BOTTOM LINE**: One-sentence final recommendation.

Rules:
- Always cite specific clause names and scores from the provided data
- If a topic is NOT in the provided clauses, say "This document does not address [topic]"
- Be decisive — give a clear verdict, not "it depends"
- Keep each section tight and scannable
"""

_FOLLOWUP_PROMPT = """\
Given this legal document Q&A:
Question: {question}
Answer summary: {answer_start}

Suggest 3 smart follow-up questions the user might want to ask next.
Return only the questions, one per line, no numbering or punctuation at the end.
Keep them short (under 10 words each)."""


# ── Embedding model ───────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _embed_model():
    if not _NUMPY_OK:
        return None
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        print(f'[chat] embeddings unavailable (using keyword fallback): {e}', file=sys.stderr)
        return None


def _encode(texts):
    model = _embed_model()
    if model is None or np is None:
        return None
    try:
        return model.encode(texts, normalize_embeddings=True,
                            batch_size=64, show_progress_bar=False)
    except Exception as e:
        print(f'[chat] encode error: {e}', file=sys.stderr)
        return None


# ── RAG pipeline ──────────────────────────────────────────────────────────────

def _bi_encode_search(clauses: list[Clause], query: str, limit: int) -> list[tuple[float, Clause]]:
    texts = [f"{c.category or ''}: {c.clause_text[:300]}" for c in clauses]
    q_vec = _encode(query)
    c_vecs = _encode(texts)
    if q_vec is None or c_vecs is None or np is None:
        return _keyword_scored(clauses, query, limit)
    scores = [float(np.dot(q_vec, cv)) for cv in c_vecs]
    return sorted(zip(scores, clauses), key=lambda x: x[0], reverse=True)[:limit]


def _keyword_scored(clauses: list[Clause], query: str,
                    limit: int) -> list[tuple[float, Clause]]:
    kws = [w.lower() for w in query.split() if len(w) > 2]
    scored = []
    for c in clauses:
        body = f"{c.category or ''} {c.clause_text} {c.plain_english or ''}".lower()
        s = sum(3.0 if kw in (c.category or '').lower() else (1.0 if kw in body else 0.0) for kw in kws)
        scored.append((s, c))
    return sorted(scored, key=lambda x: x[0], reverse=True)[:limit]


def _quick_groq(prompt: str, max_tokens: int = 120) -> str | None:
    """Fast single-shot Groq call for auxiliary tasks (HyDE, expansion, follow-ups)."""
    if not settings.groq_api_key:
        return None
    try:
        r = requests.post(
            _GROQ_URL,
            headers={'Authorization': f'Bearer {settings.groq_api_key}',
                     'Content-Type': 'application/json'},
            json={'model': _GROQ_MODEL,
                  'messages': [{'role': 'user', 'content': prompt}],
                  'max_tokens': max_tokens, 'temperature': 0.1},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f'[chat] quick_groq: {e}', file=sys.stderr)
    return None


def _hyde_retrieve(clauses: list[Clause], question: str, limit: int = 10) -> list[Clause]:
    """
    HyDE — Hypothetical Document Embeddings.
    Generate a hypothetical legal clause that would answer the question,
    then embed that to find semantically similar real clauses.
    Much better than embedding the raw question directly.
    """
    hyde_prompt = (
        f"Write 2-3 sentences of actual contract clause text that would be relevant to "
        f"this question about a legal document: '{question}'. "
        f"Write it as formal contract language, not as an answer."
    )
    hypothetical = _quick_groq(hyde_prompt, max_tokens=100) or question
    pairs = _bi_encode_search(clauses, hypothetical, limit)
    return [c for _, c in pairs]


def _multi_query_retrieve(clauses: list[Clause], question: str, limit: int = 10) -> list[Clause]:
    """
    Multi-query expansion + Reciprocal Rank Fusion.
    Decompose the question into 3 sub-queries, search each,
    then merge results using RRF to get the best combined ranking.
    """
    expansion_prompt = (
        f'For the legal question: "{question}"\n'
        f'Generate 3 different search queries to find relevant contract clauses.\n'
        f'Return only the queries, one per line, no numbering.'
    )
    expanded = _quick_groq(expansion_prompt, max_tokens=80)
    queries = [question]
    if expanded:
        queries += [q.strip() for q in expanded.split('\n') if q.strip()][:3]

    # RRF: score = sum(1 / (rank + 60)) for each query where clause appears
    rrf_scores: dict[int, tuple[float, Clause]] = {}
    for q in queries:
        ranked = _bi_encode_search(clauses, q, limit)
        for rank, (_, c) in enumerate(ranked):
            key = id(c)
            prev = rrf_scores.get(key, (0.0, c))
            rrf_scores[key] = (prev[0] + 1.0 / (rank + 60), c)

    merged = sorted(rrf_scores.values(), key=lambda x: x[0], reverse=True)
    return [c for _, c in merged[:limit]]


def _advanced_rag(clauses: list[Clause], question: str) -> list[Clause]:
    """
    Full RAG pipeline:
    1. Always include critical + high risk clauses
    2. HyDE retrieval for question-specific clauses
    3. Multi-query expansion for broad coverage
    4. Merge all results, deduplicate
    """
    risky = [c for c in clauses if c.risk_level in ('critical', 'high')]

    use_groq = bool(settings.groq_api_key)
    if use_groq:
        hyde_results  = _hyde_retrieve(clauses, question, 6)
        multi_results = _multi_query_retrieve(clauses, question, 6)
        extras = hyde_results + multi_results
    else:
        extras = [c for _, c in _bi_encode_search(clauses, question, 8)]

    seen: set = set()
    selected: list[Clause] = []
    for c in risky + extras:
        if id(c) not in seen:
            seen.add(id(c))
            selected.append(c)
        if len(selected) >= 14:
            break

    return selected or clauses[:8]


# ── Context builder ───────────────────────────────────────────────────────────

def _build_context(document: Document, clauses: list[Clause], question: str) -> str:
    counts = {l: sum(1 for c in clauses if c.risk_level == l)
              for l in ('critical', 'high', 'medium', 'low')}
    total = len(clauses)
    overview = (
        f"Document: {document.filename}\n"
        f"Overall risk: {document.overall_risk_level.upper()} "
        f"(composite score {document.overall_risk_score}/100)\n"
        f"Clause breakdown — Critical: {counts['critical']}, High: {counts['high']}, "
        f"Medium: {counts['medium']}, Low: {counts['low']} (total: {total})"
    )

    selected = _advanced_rag(clauses, question)

    blocks = '\n\n'.join(
        f"[{(c.risk_level or 'unknown').upper()}] {c.category or 'General'} "
        f"| Risk Score: {c.risk_score} | Percentile: {c.percentile}\n"
        f"Standard clause: {'Yes' if c.is_standard else 'No — unusual'}\n"
        f"Text: {c.clause_text}\n"
        + (f"Plain English: {c.plain_english}" if c.plain_english else '')
        for c in selected
    )

    return f"{overview}\n{'─'*60}\nCLAUSES FOR ANALYSIS:\n\n{blocks}"


# ── Groq streaming ────────────────────────────────────────────────────────────

def _groq_stream(messages: list[dict]):
    """Stream tokens from Groq Llama 3.3 70B."""
    if not settings.groq_api_key:
        yield 'Groq API key not set. Add GROQ_API_KEY to .env (free at console.groq.com).'
        return
    try:
        resp = requests.post(
            _GROQ_URL,
            headers={'Authorization': f'Bearer {settings.groq_api_key}',
                     'Content-Type': 'application/json'},
            json={'model': _GROQ_MODEL, 'messages': messages,
                  'max_tokens': 1024, 'temperature': 0.3, 'stream': True},
            stream=True, timeout=60,
        )
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith(b'data: '):
                data = line[6:].decode('utf-8')
                if data == '[DONE]':
                    return
                try:
                    chunk = json.loads(data)
                    text = chunk['choices'][0]['delta'].get('content', '')
                    if text:
                        yield text
                except Exception:
                    pass
    except Exception as e:
        print(f'[chat] stream error: {e}', file=sys.stderr)
        yield f'\n[Stream error: {e}]'


def _groq_sync(messages: list[dict]) -> str | None:
    """Non-streaming Groq call."""
    if not settings.groq_api_key:
        return None
    try:
        r = requests.post(
            _GROQ_URL,
            headers={'Authorization': f'Bearer {settings.groq_api_key}',
                     'Content-Type': 'application/json'},
            json={'model': _GROQ_MODEL, 'messages': messages,
                  'max_tokens': 1024, 'temperature': 0.3},
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f'[chat] groq sync error: {e}', file=sys.stderr)
    return None


def _hf_sync(context: str, history: list, question: str) -> str | None:
    """HuggingFace Mistral 7B — free fallback."""
    turns = ''.join(
        f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}\n"
        for m in history[-4:]
    )
    prompt = (
        f"<s>[INST] {_SYSTEM}\n\n{context}\n\n{'─'*40}\n"
        f"{turns}User: {question} [/INST]"
    )
    try:
        headers: dict = {'Content-Type': 'application/json'}
        if settings.huggingface_api_key:
            headers['Authorization'] = f'Bearer {settings.huggingface_api_key}'
        r = requests.post(
            'https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3',
            headers=headers,
            json={'inputs': prompt, 'parameters': {
                'max_new_tokens': 512, 'temperature': 0.3, 'return_full_text': False}},
            timeout=40,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                return data[0].get('generated_text', '').strip() or None
    except Exception as e:
        print(f'[chat] HF error: {e}', file=sys.stderr)
    return None


def _local_answer(document: Document, clauses: list[Clause], question: str) -> str:
    """Always-works local structured answer using semantic search."""
    risky  = [c for c in clauses if c.risk_level in ('critical', 'high')]
    counts = {l: sum(1 for c in clauses if c.risk_level == l)
              for l in ('critical', 'high', 'medium', 'low')}
    hits   = [c for _, c in _bi_encode_search(clauses, question, 4)]

    def fmt(c: Clause) -> str:
        return (
            f"**{c.category}** ({c.risk_level.upper()}, score {c.risk_score})\n"
            f"{c.clause_text}\n"
            + (f"*{c.plain_english}*" if c.plain_english else '')
        )

    header = (
        f"**{document.filename}** — {document.overall_risk_level.upper()} risk "
        f"({document.overall_risk_score}/100) | "
        f"Crit: {counts['critical']} · High: {counts['high']} · "
        f"Med: {counts['medium']} · Low: {counts['low']}"
    )

    q = question.lower()
    if any(w in q for w in ['sign', 'safe', 'okay', 'proceed']):
        if not risky:
            return f"{header}\n\n✅ No critical or high-risk clauses. Safe to sign."
        names = ', '.join(c.category for c in risky if c.category)
        return (f"{header}\n\n⚠️ **Review before signing** — {len(risky)} risky: **{names}**\n\n"
                + '\n\n---\n\n'.join(fmt(c) for c in risky[:3]))

    if hits:
        return f"{header}\n\n**Relevant clauses:**\n\n" + '\n\n---\n\n'.join(fmt(c) for c in hits)

    return (f"{header}\n\n"
            + ('\n\n---\n\n'.join(fmt(c) for c in risky[:3]) if risky else 'No critical or high-risk clauses.')
            + "\n\n*Add GROQ_API_KEY to .env for full AI answers (free at console.groq.com)*")


def _generate_followups(question: str, answer_start: str) -> list[str]:
    prompt = _FOLLOWUP_PROMPT.format(
        question=question, answer_start=answer_start[:200])
    result = _quick_groq(prompt, max_tokens=80)
    if not result:
        return []
    return [q.strip() for q in result.split('\n') if q.strip()][:3]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_document_and_clauses(document_id: UUID, current_user, db: Session):
    document = db.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found.')
    if document.status != 'complete':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Document is still processing.')
    clauses = list(db.scalars(select(Clause).where(Clause.document_id == document_id)).all())
    return document, clauses


def _build_messages(system: str, context: str, history: list, question: str) -> list[dict]:
    return [
        {'role': 'system', 'content': system},
        *[{'role': m.role, 'content': m.content} for m in history],
        {'role': 'user', 'content': f"{context}\n{'─'*60}\nUser question: {question}"},
    ]


# ── Streaming endpoint ────────────────────────────────────────────────────────

@router.post('/{document_id}/stream')
def chat_stream(
    document_id: UUID,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    document, clauses = _get_document_and_clauses(document_id, current_user, db)
    context  = _build_context(document, clauses, payload.question)
    messages = _build_messages(_SYSTEM, context, payload.history, payload.question)

    collected: list[str] = []

    def generate():
        for token in _groq_stream(messages):
            collected.append(token)
            yield f"data: {json.dumps({'chunk': token})}\n\n"

        full_answer = ''.join(collected)
        followups = _generate_followups(payload.question, full_answer)
        yield f"data: {json.dumps({'followups': followups, 'done': True})}\n\n"

    return StreamingResponse(generate(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# ── Non-streaming fallback ────────────────────────────────────────────────────

@router.post('/{document_id}', response_model=ChatResponse)
def chat(
    document_id: UUID,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    document, clauses = _get_document_and_clauses(document_id, current_user, db)
    context  = _build_context(document, clauses, payload.question)
    messages = _build_messages(_SYSTEM, context, payload.history, payload.question)

    answer = (
        _groq_sync(messages)
        or _hf_sync(context, payload.history, payload.question)
        or _local_answer(document, clauses, payload.question)
    )
    return ChatResponse(answer=answer)
