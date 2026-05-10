"""
Obligations & Deadline Extractor
==================================
Uses Groq to extract all actionable obligations from a contract:
payment dates, renewal windows, notice periods, non-compete durations, etc.
Returns a structured timeline the user must act on.
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
from app.models.schema import Document, User

router = APIRouter(prefix='/obligations', tags=['obligations'])
settings = get_settings()

_GROQ_URL   = 'https://api.groq.com/openai/v1/chat/completions'
_GROQ_MODEL = 'llama-3.3-70b-versatile'


class Obligation(BaseModel):
    category: str
    description: str
    deadline: str | None = None
    party: str | None = None
    urgency: str = 'medium'  # low | medium | high | critical


class ContractMeta(BaseModel):
    contract_type: str
    parties: list[str]
    effective_date: str | None
    expiration_date: str | None


class ObligationsResponse(BaseModel):
    contract_meta: ContractMeta
    obligations: list[Obligation]
    summary: str


_EXTRACT_PROMPT = """\
You are a legal analyst. Extract ALL obligations, deadlines, and important dates from this contract text.

Return a JSON object exactly matching this schema (no markdown, raw JSON only):
{
  "contract_type": "NDA | Employment Agreement | SaaS Agreement | Freelance Contract | Service Agreement | Rental Agreement | Other",
  "parties": ["Party A name", "Party B name"],
  "effective_date": "date string or null",
  "expiration_date": "date string or null",
  "obligations": [
    {
      "category": "Payment | Renewal | Notice | Non-Compete | Confidentiality | Delivery | Termination | Reporting | Other",
      "description": "plain English description of what must be done",
      "deadline": "specific date/timeframe or null",
      "party": "who must do this: Signer | Counter-party | Both | Unknown",
      "urgency": "low | medium | high | critical"
    }
  ],
  "summary": "2-sentence plain English summary of the most important obligations"
}

Extract EVERY obligation. Mark as critical if there are financial penalties or legal consequences for missing it.
"""


def _extract_with_groq(raw_text: str) -> dict | None:
    if not settings.groq_api_key:
        return None
    try:
        resp = requests.post(
            _GROQ_URL,
            headers={'Authorization': f'Bearer {settings.groq_api_key}', 'Content-Type': 'application/json'},
            json={
                'model': _GROQ_MODEL,
                'messages': [
                    {'role': 'system', 'content': _EXTRACT_PROMPT},
                    {'role': 'user',   'content': f"Contract text:\n\n{raw_text[:8000]}"},
                ],
                'max_tokens': 2048,
                'temperature': 0.1,
                'response_format': {'type': 'json_object'},
            },
            timeout=40,
        )
        if resp.status_code == 200:
            import json
            return json.loads(resp.json()['choices'][0]['message']['content'])
    except Exception as e:
        print(f'[obligations] Groq error: {e}', file=sys.stderr)
    return None


def _keyword_extract(raw_text: str, filename: str) -> dict:
    """Fallback extraction using keyword patterns."""
    import re
    text_lower = raw_text.lower()

    # Detect contract type
    types = {
        'NDA': ['non-disclosure', 'confidential', 'nda'],
        'Employment Agreement': ['employment', 'employee', 'employer', 'salary', 'compensation'],
        'SaaS Agreement': ['software', 'saas', 'subscription', 'license', 'api'],
        'Freelance Contract': ['freelance', 'contractor', 'independent contractor', 'deliverable'],
        'Rental Agreement': ['rent', 'lease', 'tenant', 'landlord', 'premises'],
        'Service Agreement': ['service', 'services', 'client', 'provider', 'deliverable'],
    }
    contract_type = 'Other'
    best_score = 0
    for ctype, keywords in types.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            contract_type = ctype

    # Find date patterns
    dates = re.findall(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', raw_text)

    # Build basic obligations from clause text
    obligations = []
    patterns = [
        (r'payment.{0,80}due.{0,40}(?:within|by|before)\s+([^.]{5,40})', 'Payment', 'high'),
        (r'(?:notice|notification).{0,60}(?:within|at least|no less than)\s+([^.]{5,40})', 'Notice', 'medium'),
        (r'(?:auto.renew|automatically renew|renewal).{0,100}', 'Renewal', 'high'),
        (r'non.compete.{0,100}', 'Non-Compete', 'critical'),
        (r'confidential.{0,60}(?:remain|for|period).{0,40}(?:year|month).{0,20}', 'Confidentiality', 'medium'),
        (r'terminat.{0,80}(?:within|upon|after)\s+([^.]{5,40})', 'Termination', 'medium'),
    ]
    for pattern, category, urgency in patterns:
        matches = re.findall(pattern, text_lower[:6000])
        if matches:
            for m in matches[:2]:
                obligations.append({
                    'category': category,
                    'description': f'Review the {category.lower()} provisions in detail.',
                    'deadline': str(m)[:80] if isinstance(m, str) else None,
                    'party': 'Both',
                    'urgency': urgency,
                })

    return {
        'contract_type': contract_type,
        'parties': [],
        'effective_date': dates[0] if dates else None,
        'expiration_date': dates[-1] if len(dates) > 1 else None,
        'obligations': obligations or [{'category': 'Review', 'description': 'Review all clauses carefully before signing.', 'deadline': None, 'party': 'Signer', 'urgency': 'medium'}],
        'summary': f'This appears to be a {contract_type}. Review all obligations carefully before signing.',
    }


@router.get('/{document_id}', response_model=ObligationsResponse)
def get_obligations(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ObligationsResponse:
    document = db.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found.')
    if document.status != 'complete':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Document is still processing.')

    raw_text = document.raw_text or ''

    data = _extract_with_groq(raw_text) or _keyword_extract(raw_text, document.filename)

    return ObligationsResponse(
        contract_meta=ContractMeta(
            contract_type=data.get('contract_type', 'Unknown'),
            parties=data.get('parties', []),
            effective_date=data.get('effective_date'),
            expiration_date=data.get('expiration_date'),
        ),
        obligations=[Obligation(**o) for o in data.get('obligations', [])],
        summary=data.get('summary', ''),
    )
