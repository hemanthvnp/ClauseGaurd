from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import fitz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.schema import Clause, Document, User
from app.ml.claude_explainer import get_claude_explainer
from app.ml.clause_classifier import get_classifier
from app.ml.clause_segmenter import ClauseSegmenter
from app.ml.risk_scorer import risk_scorer

settings = get_settings()
segmenter = ClauseSegmenter()
classifier = get_classifier()
explainer = get_claude_explainer()

DEMO_EMAIL = 'demo@clauseguard.ai'
DEMO_PASSWORD = 'ClauseGuard123!'
DEMO_FILENAME = 'ClauseGuard Demo Contract.pdf'

DEMO_TEXT = '''
1. Governing Law. This Agreement is governed by the laws of Delaware.
2. Arbitration. Any dispute must be resolved by binding arbitration in New York.
3. Limitation of Liability. Each party's liability is limited to fees paid in the prior 12 months.
4. Confidentiality. The parties must keep confidential information private.
5. Auto-Renewal. This agreement will automatically renew unless either party gives notice 30 days before the end of the term.
'''.strip()


def _storage_path() -> Path:
    path = Path(settings.processing_storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _demo_pdf_path() -> Path:
    path = _storage_path() / 'demo'
    path.mkdir(parents=True, exist_ok=True)
    return path / 'clauseguard-demo-contract.pdf'


def _create_demo_pdf(path: Path) -> None:
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    y = 48
    page.insert_text((48, y), 'ClauseGuard Demo Contract', fontsize=18, fontname='helv')
    y += 28
    page.insert_text((48, y), 'This document is generated automatically to make the app immediately usable.', fontsize=10, fontname='helv')
    y += 24
    for paragraph in DEMO_TEXT.split('\n'):
        page.insert_text((48, y), paragraph, fontsize=11, fontname='helv')
        y += 20
    pdf.save(path)
    pdf.close()


def _process_demo_document(db: Session, document: Document) -> None:
    if db.scalar(select(Clause).where(Clause.document_id == document.id)) is not None:
        return

    segments = segmenter.segment(DEMO_TEXT)
    risk_levels: list[str] = []
    total_score = 0.0
    for segment in segments:
        classification = classifier.classify(segment.text)
        assessment = risk_scorer.score(classification.category, segment.text, classification.confidence)
        explanation = explainer.explain(classification.category, assessment.risk_level, segment.text)
        db.add(
            Clause(
                document_id=document.id,
                clause_text=segment.text,
                category=classification.category,
                risk_level=assessment.risk_level,
                risk_score=assessment.risk_score,
                is_standard=assessment.is_standard,
                percentile=assessment.percentile,
                plain_english=explanation,
                position_start=segment.start,
                position_end=segment.end,
            )
        )
        risk_levels.append(assessment.risk_level)
        total_score += assessment.risk_score

    document.raw_text = DEMO_TEXT
    document.overall_risk_score = round(total_score / max(len(segments), 1), 2)
    document.overall_risk_level = max(risk_levels, key=lambda level: {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(level, 0), default='low')
    document.status = 'complete'


def seed_demo_data() -> None:
    """Create a demo user and sample contract if the database is empty."""
    db = SessionLocal()
    try:
        existing_user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing_user is None:
            demo_user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
            db.add(demo_user)
            db.commit()
            db.refresh(demo_user)
        else:
            demo_user = existing_user

        existing_document = db.scalar(select(Document).where(Document.user_id == demo_user.id))
        if existing_document is None:
            pdf_path = _demo_pdf_path()
            if not pdf_path.exists():
                _create_demo_pdf(pdf_path)

            document = Document(
                user_id=demo_user.id,
                filename=DEMO_FILENAME,
                file_type='pdf',
                s3_key=f'demo/{pdf_path.name}',
                status='processing',
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            _process_demo_document(db, document)
            db.commit()
    finally:
        db.close()
