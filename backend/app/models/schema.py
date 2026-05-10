from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

RiskLevel = Literal['critical', 'high', 'medium', 'low']
DocumentStatus = Literal['processing', 'complete', 'failed']


class User(Base):
    __tablename__ = 'users'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    documents: Mapped[list[Document]] = relationship(back_populates='user', cascade='all, delete-orphan')
    signatures: Mapped[list[Signature]] = relationship(back_populates='user', cascade='all, delete-orphan')
    comparisons: Mapped[list[Comparison]] = relationship(back_populates='user', cascade='all, delete-orphan')


class Document(Base):
    __tablename__ = 'documents'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str] = mapped_column(String, nullable=False)
    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    overall_risk_score: Mapped[float | None] = mapped_column(Float)
    overall_risk_level: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='processing', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates='documents')
    clauses: Mapped[list[Clause]] = relationship(back_populates='document', cascade='all, delete-orphan')
    signatures: Mapped[list[Signature]] = relationship(back_populates='document', cascade='all, delete-orphan')


class Clause(Base):
    __tablename__ = 'clauses'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)
    clause_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String)
    risk_level: Mapped[str | None] = mapped_column(String)
    risk_score: Mapped[float | None] = mapped_column(Float)
    is_standard: Mapped[bool | None] = mapped_column(Boolean)
    percentile: Mapped[float | None] = mapped_column(Float)
    plain_english: Mapped[str | None] = mapped_column(Text)
    position_start: Mapped[int | None] = mapped_column(Integer)
    position_end: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    document: Mapped[Document] = relationship(back_populates='clauses')


class Signature(Base):
    __tablename__ = 'signatures'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    signature_image: Mapped[str | None] = mapped_column(Text)
    document_hash: Mapped[str] = mapped_column(String, nullable=False)
    signed_pdf_s3_key: Mapped[str] = mapped_column(String, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    document: Mapped[Document] = relationship(back_populates='signatures')
    user: Mapped[User] = relationship(back_populates='signatures')


class Comparison(Base):
    __tablename__ = 'comparisons'

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    document_v1_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)
    document_v2_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)
    diff_result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates='comparisons')


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal['bearer'] = 'bearer'


class RefreshRequest(BaseModel):
    refresh_token: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    created_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    filename: str
    file_type: str
    s3_key: str
    raw_text: str | None = None
    overall_risk_score: float | None = None
    overall_risk_level: str | None = None
    status: str
    download_url: str | None = None
    created_at: datetime


class DocumentStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    overall_risk_score: float | None = None
    overall_risk_level: str | None = None


class ClauseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    clause_text: str
    category: str | None = None
    risk_level: str | None = None
    risk_score: float | None = None
    is_standard: bool | None = None
    percentile: float | None = None
    plain_english: str | None = None
    position_start: int | None = None
    position_end: int | None = None
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    document: DocumentRead
    message: str


class UploadMetadata(BaseModel):
    filename: str
    file_type: Literal['pdf', 'docx']


class CompareRequest(BaseModel):
    document_v1_id: UUID
    document_v2_id: UUID


class CompareRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    document_v1_id: UUID
    document_v2_id: UUID
    diff_result: dict
    created_at: datetime


class SignatureRequest(BaseModel):
    signature_image: str | None = None


class SignatureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    user_id: UUID
    signature_image: str | None = None
    document_hash: str
    signed_pdf_s3_key: str
    download_url: str | None = None
    signed_at: datetime


class AnalyzeTextRequest(BaseModel):
    text: str
    source_url: str | None = None
    title: str | None = None


class AnalyzeTextClause(BaseModel):
    text: str
    category: str
    risk_level: str
    risk_score: float
    is_standard: bool
    percentile: float
    explanation: str


class AnalyzeTextResponse(BaseModel):
    summary: dict[str, int]
    clauses: list[AnalyzeTextClause]
    overall_risk_score: float
    overall_risk_level: str


class ClausePipelineResult(BaseModel):
    clause_text: str
    category: str
    risk_level: str
    risk_score: float
    is_standard: bool
    percentile: float
    plain_english: str
    position_start: int
    position_end: int


class DemoBootstrapResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal['bearer'] = 'bearer'
    user: UserRead
    documents: list[DocumentRead]


class ChatMessage(BaseModel):
    role: Literal['user', 'assistant']
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    answer: str
