from __future__ import annotations

from difflib import SequenceMatcher
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schema import Clause, CompareRead, CompareRequest, Comparison, Document, User

router = APIRouter(prefix='/compare', tags=['compare'])


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


@router.post('', response_model=CompareRead, status_code=status.HTTP_201_CREATED)
def compare_documents(payload: CompareRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Comparison:
    document_v1 = db.get(Document, payload.document_v1_id)
    document_v2 = db.get(Document, payload.document_v2_id)
    if document_v1 is None or document_v2 is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='One or both documents were not found.')
    if document_v1.user_id != current_user.id or document_v2.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='You do not own one or both documents.')
    if payload.document_v1_id == payload.document_v2_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Select two different documents to compare.')

    clauses_v1 = list(db.scalars(select(Clause).where(Clause.document_id == payload.document_v1_id).order_by(Clause.position_start.asc())).all())
    clauses_v2 = list(db.scalars(select(Clause).where(Clause.document_id == payload.document_v2_id).order_by(Clause.position_start.asc())).all())

    shared_length = min(len(clauses_v1), len(clauses_v2))
    unchanged: list[dict] = []
    modified: list[dict] = []
    risk_changed: list[dict] = []

    for index in range(shared_length):
        left = clauses_v1[index]
        right = clauses_v2[index]
        similarity = _similarity(left.clause_text, right.clause_text)
        if similarity >= 0.92 and left.risk_level == right.risk_level:
            unchanged.append({'index': index, 'text': right.clause_text})
        else:
            if left.risk_level != right.risk_level:
                risk_changed.append({
                    'index': index,
                    'from': left.risk_level,
                    'to': right.risk_level,
                    'category': right.category,
                })
            modified.append({
                'index': index,
                'from': left.clause_text,
                'to': right.clause_text,
                'similarity': round(similarity, 3),
            })

    added = [{'index': index, 'text': clause.clause_text, 'category': clause.category} for index, clause in enumerate(clauses_v2[shared_length:], start=shared_length)]
    removed = [{'index': index, 'text': clause.clause_text, 'category': clause.category} for index, clause in enumerate(clauses_v1[shared_length:], start=shared_length)]

    diff_result = {
        'added': added,
        'removed': removed,
        'modified': modified,
        'risk_changed': risk_changed,
        'unchanged_count': len(unchanged),
    }

    comparison = Comparison(
        user_id=current_user.id,
        document_v1_id=payload.document_v1_id,
        document_v2_id=payload.document_v2_id,
        diff_result=diff_result,
    )
    db.add(comparison)
    db.commit()
    db.refresh(comparison)
    return comparison


@router.get('/{comparison_id}', response_model=CompareRead)
def get_comparison(comparison_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Comparison:
    comparison = db.get(Comparison, comparison_id)
    if comparison is None or comparison.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comparison not found.')
    return comparison
