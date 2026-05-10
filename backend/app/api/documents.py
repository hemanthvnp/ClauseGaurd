from __future__ import annotations

import shutil
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schema import Clause, ClauseRead, Document, DocumentRead, DocumentStatusRead, DocumentUploadResponse, User
from app.tasks.document_processor import file_response_for_document, process_document

router = APIRouter(prefix='/documents', tags=['documents'])
settings = get_settings()

_MAX_PAGE_SIZE = 100


def _storage_dir() -> Path:
    path = Path(settings.processing_storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post('/upload', response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    suffix = Path(file.filename).suffix.lower()
    file_type = 'pdf' if suffix == '.pdf' else 'docx' if suffix == '.docx' else ''
    if file_type == '':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Only PDF and DOCX files are supported.')

    max_bytes = settings.max_upload_mb * 1024 * 1024
    file_bytes = await file.read()
    if len(file_bytes) > max_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'File exceeds maximum size of {settings.max_upload_mb} MB.')

    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded file is empty.')

    filename = file.filename or f'document-{uuid4()}{suffix}'
    safe_name = f'{uuid4()}-{filename}'.replace(' ', '_')
    storage_path = _storage_dir() / safe_name
    storage_path.write_bytes(file_bytes)

    document = Document(
        user_id=current_user.id,
        filename=filename,
        file_type=file_type,
        s3_key=safe_name,
        status='processing',
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    process_document.delay(str(document.id))
    return DocumentUploadResponse(document=_document_with_download_url(document), message='Upload accepted. Processing has started.')


def _document_with_download_url(document: Document) -> Document:
    document.download_url = f'/api/v1/documents/{document.id}/download'
    return document


@router.get('/', response_model=list[DocumentRead])
def list_documents(
    skip: int = Query(default=0, ge=0, description='Number of documents to skip'),
    limit: int = Query(default=50, ge=1, le=_MAX_PAGE_SIZE, description='Maximum number of documents to return'),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    documents = list(
        db.scalars(
            select(Document)
            .where(Document.user_id == current_user.id)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).all()
    )
    for document in documents:
        document.download_url = f'/api/v1/documents/{document.id}/download'
    return documents


@router.get('/{document_id}', response_model=DocumentRead)
def get_document(document_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found.')
    document.download_url = f'/api/v1/documents/{document.id}/download'
    return document


@router.get('/{document_id}/clauses', response_model=list[ClauseRead])
def get_clauses(document_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Clause]:
    document = db.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found.')
    return list(db.scalars(select(Clause).where(Clause.document_id == document_id).order_by(Clause.position_start.asc())).all())


@router.get('/{document_id}/status', response_model=DocumentStatusRead)
def get_status(document_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found.')
    document.download_url = f'/api/v1/documents/{document.id}/download'
    return document


@router.get('/{document_id}/download')
def download_document(document_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    document = db.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found.')
    return file_response_for_document(document)


@router.delete('/{document_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    document = db.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found.')

    # Remove physical files before deleting DB record
    storage = _storage_dir()
    for candidate in (storage / document.s3_key, storage / 'signed' / f'{document.id}.pdf'):
        try:
            if candidate.exists():
                candidate.unlink()
        except OSError:
            pass

    db.execute(delete(Clause).where(Clause.document_id == document_id))
    db.delete(document)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
