from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schema import Clause, Document, Signature, SignatureRead, SignatureRequest, User
from app.tasks.document_processor import build_signed_pdf, file_response_for_signed_document, sha256_of_file

router = APIRouter(prefix='/sign', tags=['sign'])
settings = get_settings()

_MAX_SIGNATURE_BYTES = 2 * 1024 * 1024  # 2 MB


def _validate_signature_image(image: str | None) -> None:
    """Validate that signature_image is a properly-encoded PNG/JPEG data URL."""
    if image is None:
        return
    if not image.startswith('data:image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Signature must be a base64-encoded image data URL (e.g. data:image/png;base64,...).',
        )
    if ',' not in image:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid signature image format: missing base64 payload.',
        )
    if len(image.encode('utf-8')) > _MAX_SIGNATURE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Signature image is too large (maximum 2 MB).',
        )
    try:
        _, data = image.split(',', 1)
        base64.b64decode(data, validate=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Signature image contains invalid base64 data.',
        ) from exc


@router.post('/{document_id}', response_model=SignatureRead, status_code=status.HTTP_201_CREATED)
def sign_document(
    document_id: UUID,
    payload: SignatureRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Signature:
    _validate_signature_image(payload.signature_image)

    document = db.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found.')
    if document.status != 'complete':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Document must be fully processed before signing.')

    file_path = Path(settings.processing_storage_path) / document.s3_key
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Original document file not found.')

    document_hash = sha256_of_file(file_path)
    timestamp = datetime.now(timezone.utc).isoformat()
    signature_material = f'{document_hash}|{current_user.id}|{timestamp}|{payload.signature_image or ""}'
    signed_pdf_path = build_signed_pdf(document, file_path, payload.signature_image)
    signed_pdf_key = f'signed/{document.id}.pdf'
    signature = Signature(
        document_id=document.id,
        user_id=current_user.id,
        signature_image=payload.signature_image,
        document_hash=hashlib.sha256(signature_material.encode('utf-8')).hexdigest(),
        signed_pdf_s3_key=signed_pdf_key,
    )
    db.add(signature)
    db.commit()
    db.refresh(signature)
    document.overall_risk_level = document.overall_risk_level or 'low'
    signature.download_url = f'/api/v1/sign/{document_id}/download'
    return signature


@router.get('/{document_id}/download')
def download_signed_document(document_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    document = db.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found.')
    signature = db.scalar(select(Signature).where(Signature.document_id == document_id).order_by(Signature.signed_at.desc()))
    if signature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No signed document found. Please sign the document first.')
    return file_response_for_signed_document(signature.signed_pdf_s3_key)
