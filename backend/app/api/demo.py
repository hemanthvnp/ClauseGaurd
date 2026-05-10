from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import create_access_token, create_refresh_token
from app.models.schema import DemoBootstrapResponse, Document, User, UserRead, DocumentRead
from app.seed import DEMO_EMAIL

router = APIRouter(prefix='/demo', tags=['demo'])


@router.get('/bootstrap', response_model=DemoBootstrapResponse)
def bootstrap_demo() -> DemoBootstrapResponse:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Demo account is not available yet.')

        documents = list(db.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())).all())
        for document in documents:
            document.download_url = f'/api/v1/documents/{document.id}/download'

        subject = str(user.id)
        return DemoBootstrapResponse(
            access_token=create_access_token(subject),
            refresh_token=create_refresh_token(subject),
            user=UserRead.model_validate(user),
            documents=[DocumentRead.model_validate(document) for document in documents],
        )
    finally:
        db.close()