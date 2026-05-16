"""
Integration tests for the Documents + Analytics + Search APIs.
Uses an in-memory SQLite database and mocked external services.
"""
from __future__ import annotations

import io
import uuid


# ── Auth tests ────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": f"user_{uuid.uuid4().hex[:8]}@test.com",
            "password": "SecurePass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client, sample_user):
        resp = client.post("/api/v1/auth/register", json={
            "email": sample_user.email,
            "password": "AnotherPass123",
        })
        assert resp.status_code == 400

    def test_login_success(self, client, sample_user):
        resp = client.post("/api/v1/auth/login", json={
            "email": sample_user.email,
            "password": "testpassword123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client, sample_user):
        resp = client.post("/api/v1/auth/login", json={
            "email": sample_user.email,
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_me_requires_auth(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_returns_user(self, client, auth_headers, sample_user):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == sample_user.email


# ── Document tests ────────────────────────────────────────────────────────────

class TestDocuments:
    def test_list_documents_empty(self, client, auth_headers):
        resp = client.get("/api/v1/documents/", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_documents_with_data(self, client, auth_headers, sample_document):
        resp = client.get("/api/v1/documents/", headers=auth_headers)
        assert resp.status_code == 200
        docs = resp.json()
        assert any(str(sample_document.id) in str(d.get("id", "")) for d in docs)

    def test_get_document_detail(self, client, auth_headers, sample_document):
        resp = client.get(
            f"/api/v1/documents/{sample_document.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == sample_document.filename

    def test_get_document_not_found(self, client, auth_headers):
        resp = client.get(
            f"/api/v1/documents/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_get_clauses(self, client, auth_headers, sample_document, sample_clauses):
        resp = client.get(
            f"/api/v1/documents/{sample_document.id}/clauses",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        clauses = resp.json()
        assert len(clauses) == len(sample_clauses)

    def test_documents_require_auth(self, client):
        resp = client.get("/api/v1/documents/")
        assert resp.status_code == 401

    def test_delete_document(self, client, auth_headers, sample_document):
        resp = client.delete(
            f"/api/v1/documents/{sample_document.id}",
            headers=auth_headers,
        )
        assert resp.status_code in (200, 204)


# ── Analytics tests ───────────────────────────────────────────────────────────

class TestAnalytics:
    def test_summary_no_docs(self, client, auth_headers):
        resp = client.get("/api/v1/analytics/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_documents" in data

    def test_summary_with_docs(self, client, auth_headers, sample_document, sample_clauses):
        resp = client.get("/api/v1/analytics/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] >= 1

    def test_risk_distribution(self, client, auth_headers, sample_document, sample_clauses):
        resp = client.get("/api/v1/analytics/risk-distribution", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "distribution" in data
        assert "total" in data

    def test_category_heatmap(self, client, auth_headers, sample_document, sample_clauses):
        resp = client.get("/api/v1/analytics/category-heatmap", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_trends(self, client, auth_headers, sample_document):
        resp = client.get("/api/v1/analytics/trends?days=30", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_benchmark(self, client, auth_headers, sample_document):
        resp = client.get(
            f"/api/v1/analytics/benchmark/{sample_document.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "benchmark" in data
        assert "comparison" in data

    def test_analytics_require_auth(self, client):
        resp = client.get("/api/v1/analytics/summary")
        assert resp.status_code == 401


# ── Search tests ──────────────────────────────────────────────────────────────

class TestSearch:
    def test_search_empty_portfolio(self, client, auth_headers):
        resp = client.post(
            "/api/v1/search",
            json={"query": "arbitration clause", "top_k": 5},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_hits"] == 0

    def test_search_with_documents(
        self, client, auth_headers, sample_document, sample_clauses
    ):
        resp = client.post(
            "/api/v1/search",
            json={"query": "arbitration", "top_k": 5},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "hits" in data
        assert isinstance(data["hits"], list)

    def test_suggest_categories(self, client, auth_headers):
        resp = client.get("/api/v1/search/suggest?q=arb", headers=auth_headers)
        assert resp.status_code == 200
        suggestions = resp.json()
        assert isinstance(suggestions, list)
        assert any("Arbitration" in s for s in suggestions)

    def test_search_requires_auth(self, client):
        resp = client.post(
            "/api/v1/search",
            json={"query": "arbitration"},
        )
        assert resp.status_code == 401


# ── Health check ──────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
