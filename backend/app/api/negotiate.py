"""
AI Clause Negotiation Advisor
================================
For any high/critical clause, generates:
  1. Why this clause is risky (specific, not generic)
  2. A fairer alternative clause text the user can propose
  3. Negotiation tips — why the other party might accept the change
"""
from __future__ import annotations

import sys
from uuid import UUID

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schema import Clause, Document, User

router = APIRouter(prefix='/negotiate', tags=['negotiate'])
settings = get_settings()

_GROQ_URL   = 'https://api.groq.com/openai/v1/chat/completions'
_GROQ_MODEL = 'llama-3.3-70b-versatile'


class NegotiateRequest(BaseModel):
    clause_id: UUID


class NegotiateResponse(BaseModel):
    why_risky: str
    alternative_text: str
    negotiation_tips: str
    likelihood_of_acceptance: str


_NEGOTIATE_PROMPT = """\
You are an expert contract attorney helping an individual negotiate a risky contract clause.

Given the clause category, risk level, and text, provide:
1. WHY IT'S RISKY: 2-3 sentences explaining the specific risk to the person signing, in plain English.
2. ALTERNATIVE TEXT: A complete rewritten version of the clause that is fairer and more balanced. Write it as actual contract language.
3. NEGOTIATION TIPS: 2-3 practical tips on how to approach asking for this change. Why might the other party accept?
4. LIKELIHOOD: Rate the likelihood the other party will accept: Very Likely | Likely | Possible | Unlikely

Respond with a JSON object (no markdown):
{
  "why_risky": "...",
  "alternative_text": "...",
  "negotiation_tips": "...",
  "likelihood_of_acceptance": "Likely | Possible | ..."
}
"""


def _call_groq(category: str, risk_level: str, clause_text: str) -> dict | None:
    if not settings.groq_api_key:
        return None
    try:
        resp = requests.post(
            _GROQ_URL,
            headers={'Authorization': f'Bearer {settings.groq_api_key}', 'Content-Type': 'application/json'},
            json={
                'model': _GROQ_MODEL,
                'messages': [
                    {'role': 'system', 'content': _NEGOTIATE_PROMPT},
                    {'role': 'user', 'content': (
                        f"Category: {category}\nRisk Level: {risk_level}\n\n"
                        f"Clause text:\n{clause_text[:2000]}"
                    )},
                ],
                'max_tokens': 1024,
                'temperature': 0.3,
                'response_format': {'type': 'json_object'},
            },
            timeout=30,
        )
        if resp.status_code == 200:
            import json
            return json.loads(resp.json()['choices'][0]['message']['content'])
    except Exception as e:
        print(f'[negotiate] Groq error: {e}', file=sys.stderr)
    return None


_FALLBACK_TIPS = {
    'Arbitration': (
        "This arbitration clause removes your right to sue in court or join a class action.",
        'The parties agree to resolve disputes through arbitration or litigation at the election of the claiming party, with the venue mutually agreed upon.',
        "Many companies accept mutual arbitration clauses. Ask that both parties have the choice of forum, not just the company.",
        "Possible"
    ),
    'Uncapped Liability': (
        "This clause exposes you to unlimited financial liability with no ceiling on damages.",
        "Each party's total liability under this Agreement shall not exceed the greater of (a) the fees paid in the 12 months preceding the claim, or (b) $[amount].",
        "Liability caps are standard in commercial contracts. Propose a cap equal to the contract value or fees paid.",
        "Likely"
    ),
    'Non-Compete': (
        "This non-compete restricts your ability to work in your field and may limit your career opportunities.",
        "The restrictions in this section shall be limited to [specific geography] and shall not exceed [6-12] months from the termination date.",
        "Courts often void overly broad non-competes. Ask for narrower geography, shorter duration, and clear exceptions for your existing clients.",
        "Possible"
    ),
    'Auto-Renewal': (
        "This clause renews the contract automatically without your active consent, potentially locking you in.",
        "This Agreement shall renew for successive one-year terms unless either party provides written notice of non-renewal at least 30 days before the end of the then-current term.",
        "Auto-renewal with adequate notice is industry standard. Ask for a longer notice window (60-90 days) and email reminders.",
        "Very Likely"
    ),
    'Data Usage Rights': (
        "This clause grants broad rights to use, share, or sell your personal or business data.",
        "Company may only use Customer data to provide the contracted services and shall not share, sell, or use it for any other purpose without explicit written consent.",
        "Data protection is a strong negotiating point — cite GDPR or CCPA. Most companies will accept restrictions on selling data.",
        "Likely"
    ),
}


@router.post('/{document_id}', response_model=NegotiateResponse)
def negotiate_clause(
    document_id: UUID,
    payload: NegotiateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NegotiateResponse:
    document = db.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found.')

    clause = db.get(Clause, payload.clause_id)
    if clause is None or clause.document_id != document_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Clause not found.')

    data = _call_groq(clause.category or 'General', clause.risk_level or 'high', clause.clause_text)

    if data:
        return NegotiateResponse(
            why_risky=data.get('why_risky', ''),
            alternative_text=data.get('alternative_text', ''),
            negotiation_tips=data.get('negotiation_tips', ''),
            likelihood_of_acceptance=data.get('likelihood_of_acceptance', 'Unknown'),
        )

    # Keyword fallback
    cat = clause.category or ''
    for key, (why, alt, tips, likelihood) in _FALLBACK_TIPS.items():
        if key.lower() in cat.lower():
            return NegotiateResponse(
                why_risky=why, alternative_text=alt,
                negotiation_tips=tips, likelihood_of_acceptance=likelihood,
            )

    return NegotiateResponse(
        why_risky=f"This {cat} clause is rated {clause.risk_level} risk and may not protect your interests adequately.",
        alternative_text=f"[Propose a mutual and balanced {cat} clause with clearly defined limits, mutual obligations, and termination rights for both parties.]",
        negotiation_tips="Request that the clause be made mutual (same obligations apply to both parties). Most companies will accept mutual clauses as it reflects good faith.",
        likelihood_of_acceptance="Possible",
    )
