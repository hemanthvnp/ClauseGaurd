"""
pytest fixtures for ClauseGuard test suite.

Provides:
  - in-memory SQLite database (isolated per test)
  - FastAPI test client with auth headers
  - sample clause + document objects
  - mock LLM responses (no external API calls in tests)
"""
from __future__ import annotations

import uuid
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.schema import Clause, Document, User

# ── Test DB (SQLite in-memory) ────────────────────────────────────────────────

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db: Session) -> TestClient:
    def _get_test_db():
        yield db

    app.dependency_overrides[get_db] = _get_test_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Sample data fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def sample_user(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="test@clauseguard.ai",
        password_hash=hash_password("testpassword123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(sample_user: User) -> dict[str, str]:
    token = create_access_token(str(sample_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_document(db: Session, sample_user: User) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        filename="test_contract.pdf",
        file_type="pdf",
        s3_key="test_contract.pdf",
        raw_text="This Agreement shall be governed by the laws of California. "
                 "Disputes shall be resolved by binding arbitration.",
        overall_risk_score=72.5,
        overall_risk_level="high",
        status="complete",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@pytest.fixture
def sample_clauses(db: Session, sample_document: Document) -> list[Clause]:
    clauses_data = [
        {
            "category": "Arbitration",
            "clause_text": "Disputes shall be resolved by binding arbitration under AAA rules.",
            "risk_level": "critical",
            "risk_score": 95.0,
            "is_standard": False,
            "percentile": 95.0,
            "plain_english": "You give up your right to sue in court.",
        },
        {
            "category": "Governing Law",
            "clause_text": "This Agreement shall be governed by the laws of California.",
            "risk_level": "low",
            "risk_score": 14.0,
            "is_standard": True,
            "percentile": 14.0,
            "plain_english": "California law applies to this contract.",
        },
        {
            "category": "Non-Compete",
            "clause_text": "Employee shall not compete for 2 years post-termination.",
            "risk_level": "high",
            "risk_score": 85.0,
            "is_standard": False,
            "percentile": 85.0,
            "plain_english": "You cannot work for competitors for 2 years.",
        },
    ]
    clauses = []
    for i, data in enumerate(clauses_data):
        c = Clause(
            id=uuid.uuid4(),
            document_id=sample_document.id,
            position_start=i * 100,
            position_end=(i + 1) * 100,
            **data,
        )
        db.add(c)
        clauses.append(c)
    db.commit()
    return clauses


# ── LLM mock (prevents real API calls during tests) ───────────────────────────

@pytest.fixture(autouse=True)
def mock_llm():
    with patch("app.ml.claude_explainer.ClauseExplainer._claude", return_value=None), \
         patch("app.ml.claude_explainer.ClauseExplainer._groq", return_value="Test explanation."), \
         patch("app.ml.clause_classifier.ClauseClassifier._load_transformer_model", return_value=None):
        yield


@pytest.fixture
def mock_celery():
    with patch("app.tasks.document_processor.process_document.apply_async") as mock:
        mock.return_value = MagicMock(id="test-task-id")
        yield mock
