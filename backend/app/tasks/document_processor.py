from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID
import textwrap

import fitz
from celery import Celery
from docx import Document as DocxDocument
from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.models.schema import Clause, Document
from app.ml.claude_explainer import get_claude_explainer
from app.ml.clause_classifier import get_classifier
from app.ml.clause_segmenter import ClauseSegmenter
from app.ml.risk_scorer import risk_scorer

settings = get_settings()
celery_app = Celery('clauseguard', broker=settings.redis_url, backend=settings.redis_url)

try:
    _conn = celery_app.connection()
    _conn.ensure_connection(max_retries=1, timeout=2)
    _conn.close()
    celery_app.conf.task_always_eager = False
except Exception:
    celery_app.conf.task_always_eager = True

segmenter = ClauseSegmenter()
classifier = get_classifier()
explain = get_claude_explainer()


def _extract_pdf_text(path: Path) -> str:
    with fitz.open(path) as pdf:
        return '\n\n'.join(page.get_text('text') for page in pdf)


def _extract_docx_text(path: Path) -> str:
    doc = DocxDocument(str(path))
    return '\n'.join(paragraph.text for paragraph in doc.paragraphs)


def extract_text(path: Path, file_type: str) -> str:
    if file_type == 'pdf':
        return _extract_pdf_text(path)
    if file_type == 'docx':
        return _extract_docx_text(path)
    raise ValueError(f'Unsupported file type: {file_type}')


def _risk_level_rank(level: str) -> int:
    return {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(level, 0)


def _overall_risk_level(levels: list[str]) -> str:
    if not levels:
        return 'low'
    return max(levels, key=_risk_level_rank)


def _storage_path() -> Path:
    path = Path(settings.processing_storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _signed_storage_path() -> Path:
    path = _storage_path() / 'signed'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _append_risk_page(pdf: fitz.Document, document: Document) -> None:
    appendix = pdf.new_page(-1, width=595, height=842)
    y = 48

    def write_line(text: str, font_size: float = 10, gap: int = 16) -> None:
        nonlocal appendix, y
        if y > 790:
            appendix = pdf.new_page(-1, width=595, height=842)
            y = 48
        appendix.insert_text((48, y), text, fontsize=font_size, fontname='helv')
        y += gap

    write_line('ClauseGuard Risk Acknowledgment', font_size=18, gap=30)
    write_line(f'Document: {document.filename}', font_size=11, gap=20)
    write_line(f'Processed: {datetime.utcnow().isoformat()}Z', font_size=10, gap=24)
    write_line(f'Overall risk: {document.overall_risk_level or "unknown"} ({document.overall_risk_score or 0})', font_size=11, gap=28)
    write_line('Critical and High Risk Clauses', font_size=13, gap=22)

    risky_clauses = [
        clause for clause in document.clauses
        if (clause.risk_level or '').lower() in {'critical', 'high'}
    ]
    if not risky_clauses:
        write_line('No critical or high-risk clauses were identified.', font_size=10, gap=16)
        return

    for clause in risky_clauses:
        text = f'- [{clause.risk_level}] {clause.category or "Unclassified"}: {clause.clause_text}'
        for wrapped_line in textwrap.wrap(text, width=88) or ['']:
            write_line(wrapped_line, font_size=9, gap=14)
        y += 4


def build_signed_pdf(document: Document, source_path: Path, signature_image: str | None) -> Path:
    """Create a signed PDF from the original document and append an acknowledgement page."""
    signed_path = _signed_storage_path() / f'{document.id}.pdf'
    if document.file_type == 'pdf':
        pdf = fitz.open(source_path)
    else:
        pdf = fitz.open()
        text = document.raw_text or extract_text(source_path, document.file_type)
        page = pdf.new_page(-1, width=595, height=842)

        def write_wrapped(text_line: str, font_size: float = 10, gap: int = 14) -> None:
            nonlocal page, pdf
            y_pos = write_wrapped.y
            if y_pos > 790:
                page = pdf.new_page(-1, width=595, height=842)
                y_pos = 48
            page.insert_text((48, y_pos), text_line, fontsize=font_size, fontname='helv')
            write_wrapped.y = y_pos + gap

        write_wrapped.y = 48  # type: ignore[attr-defined]
        write_wrapped(document.filename, font_size=16, gap=28)
        write_wrapped('Original document text', font_size=12, gap=20)
        for paragraph in text.split('\n'):
            if not paragraph.strip():
                write_wrapped.y += 8  # type: ignore[attr-defined]
                continue
            for wrapped_line in textwrap.wrap(paragraph, width=92) or ['']:
                write_wrapped(wrapped_line, font_size=10, gap=14)

    _append_risk_page(pdf, document)

    if signature_image:
        try:
            image_bytes = bytes()
            if signature_image.startswith('data:image') and ',' in signature_image:
                import base64

                image_bytes = base64.b64decode(signature_image.split(',', 1)[1])
            if image_bytes:
                signature_page = pdf[-1]
                signature_page.insert_image(fitz.Rect(48, 650, 260, 760), stream=image_bytes, keep_proportion=True)
        except Exception:
            pass

    pdf.save(signed_path)
    pdf.close()
    return signed_path


@celery_app.task(name='app.tasks.document_processor.process_document')
def process_document(document_id: str) -> dict[str, Any]:
    """Process one uploaded document end-to-end.

    Input: a document UUID string.
    Output: a summary of extracted and classified clauses.
    """
    db = SessionLocal()
    try:
        document_uuid = UUID(document_id)
        document = db.get(Document, document_uuid)
        if document is None:
            raise ValueError('Document not found')

        file_path = _storage_path() / document.s3_key
        raw_text = extract_text(file_path, document.file_type)
        document.raw_text = raw_text

        existing_clauses = db.scalars(select(Clause).where(Clause.document_id == document_uuid)).all()
        for clause in existing_clauses:
            db.delete(clause)

        segments = segmenter.segment(raw_text)
        risk_levels: list[str] = []
        total_score = 0.0

        for segment in segments:
            classification = classifier.classify(segment.text)
            assessment = risk_scorer.score(classification.category, segment.text, classification.confidence)
            explanation = explain.explain(classification.category, assessment.risk_level, segment.text)
            risk_levels.append(assessment.risk_level)
            total_score += assessment.risk_score
            db.add(
                Clause(
                    document_id=document_uuid,
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

        clause_count = max(len(segments), 1)
        document.overall_risk_score = round(total_score / clause_count, 2)
        document.overall_risk_level = _overall_risk_level(risk_levels)
        document.status = 'complete'
        db.commit()
        return {
            'document_id': document_id,
            'status': document.status,
            'clause_count': len(segments),
            'overall_risk_score': document.overall_risk_score,
            'overall_risk_level': document.overall_risk_level,
        }
    except Exception as exc:
        db.rollback()
        document = db.get(Document, UUID(document_id))
        if document is not None:
            document.status = 'failed'
            db.commit()
        raise exc
    finally:
        db.close()


def file_response_for_document(document: Document) -> FileResponse:
    path = _storage_path() / document.s3_key
    if not path.exists():
        raise HTTPException(status_code=404, detail='Document file not found.')
    media_type = 'application/pdf' if document.file_type == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return FileResponse(path, media_type=media_type, filename=document.filename)


def file_response_for_signed_document(signed_key: str) -> FileResponse:
    path = _storage_path() / signed_key
    if not path.exists():
        raise HTTPException(status_code=404, detail='Signed document not found.')
    return FileResponse(path, media_type='application/pdf', filename=Path(signed_key).name)


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as file_handle:
        for chunk in iter(lambda: file_handle.read(8192), b''):
            digest.update(chunk)
    return digest.hexdigest()
