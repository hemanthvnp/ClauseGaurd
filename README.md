# ClauseGuard

AI-powered legal document risk analyzer — production-grade ML + engineering.

---

## What it does

ClauseGuard ingests PDF/DOCX contracts, runs them through a multi-stage ML pipeline,
and surfaces clause-level risk with plain-English explanations, negotiation advice,
and portfolio-wide analytics.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  Browser  (React 18 + Vite)                                        │
│  Analytics Dashboard · Chat Panel · Contradiction Alert            │
│  WebSocket Progress Bar · Cross-Document Search                    │
└──────────────┬─────────────────────────────────────────────────────┘
               │ HTTPS / WebSocket
┌──────────────▼─────────────────────────────────────────────────────┐
│  FastAPI (Python 3.11)  —  /api/v1/*  +  /ws/*  +  /metrics       │
│  Auth (JWT) · Rate Limiter (Redis token-bucket) · Audit Logger     │
│  Prometheus Middleware  ·  Readiness probe                         │
│                                                                    │
│  REST: auth · documents · chat · negotiate · obligations           │
│        compare · sign · analytics · search · batch · extension     │
└──────┬────────────────────────────┬───────────────────────────────┘
       │ enqueue                    │ pub/sub (progress events)
┌──────▼──────┐          ┌──────────▼──────┐
│  Celery     │          │  Redis 7         │
│  Worker     │          │  Cache + Broker  │
└──────┬──────┘          └─────────────────┘
       │
┌──────▼────────────────────────────────────────────────────────────┐
│  ML Pipeline  (per document)                                      │
│                                                                   │
│  1. Text Extraction    PyMuPDF / python-docx                      │
│  2. Clause Segmentation  spaCy NLP + heuristics                   │
│  3. Classification     Legal-BERT (CUAD fine-tuned) →            │
│                        zero-shot (BART-MNLI) → keyword rules      │
│                        [Platt-calibrated probabilities]           │
│  4. Risk Scoring       Category base scores + keyword modifiers   │
│  5. NER Extraction     spaCy + regex (parties, dates, amounts)    │
│  6. LLM Explanation    Claude claude-sonnet-4-6 + prompt caching →│
│                        Groq Llama 3.3 70B → HuggingFace → tmpl   │
│  7. Contradiction Det. Pairwise cosine + antonym rules            │
│  8. Vector Indexing    FAISS (all-MiniLM-L6-v2, 384-dim)         │
└──────┬────────────────────────────────────────────────────────────┘
       │
┌──────▼──────────┐  ┌────────────┐  ┌───────────────────────────┐
│  PostgreSQL 16  │  │  MinIO S3  │  │  MLflow                   │
│  Documents      │  │  Files     │  │  Experiments + Artifacts  │
│  Clauses        │  └────────────┘  └───────────────────────────┘
│  Audit Events   │
└─────────────────┘
```

---

## ML / Applied-ML Highlights

| Feature | Implementation |
|---|---|
| Clause classification | Legal-BERT fine-tuned on CUAD (41 categories) + Platt scaling |
| Semantic search | FAISS IndexFlatIP + BM25 hybrid + Reciprocal Rank Fusion |
| RAG pipeline | HyDE + multi-query expansion + RRF fusion |
| Contradiction detection | Pairwise cosine similarity + keyword antonym rules + risk-signal conflicts |
| NER extraction | spaCy + regex (parties, dates, monetary values, jurisdiction) |
| LLM explanations | Anthropic Claude with **prompt caching** (~80% input token savings) |
| Risk calibration | Platt scaling (fitted on CUAD dev set) |
| Evaluation | CUAD benchmark — accuracy, macro-F1, per-category P/R/F1 |
| Experiment tracking | MLflow — params, metrics, model artifacts |
| Training | `scripts/train_legal_bert.py` — full CUAD fine-tuning pipeline |

---

## SDE / Engineering Highlights

| Feature | Implementation |
|---|---|
| Real-time updates | WebSocket (`/ws/document/{id}`) via Redis pub/sub |
| Rate limiting | Redis token-bucket (per-user, per-endpoint, Lua atomic script) |
| Observability | Prometheus metrics + Grafana dashboards + structured logs |
| Audit logging | JSON events → PostgreSQL `audit_events` (SOC 2 / GDPR ready) |
| Async processing | Celery + Redis, Flower monitoring |
| Batch analysis | Up to 10 documents in parallel via Celery group |
| Portfolio analytics | Risk distribution, category heatmap, trend chart, benchmark |
| Test suite | pytest — ML unit tests + API integration tests + mock LLM |
| CI/CD | GitHub Actions — ruff, mypy, pytest, CUAD eval, Docker, bandit |
| Security | JWT, bcrypt, CORS, Bandit SAST, TruffleHog secret scanning |

---

## Quick Start

```bash
git clone <repo-url>
cd ClauseGaurd
cp .env.example .env      # add your keys (see below)
docker compose up -d
open http://localhost:5173
```

Minimum `.env`:
```env
GROQ_API_KEY=gsk_...             # free — console.groq.com
JWT_SECRET=change-me-64-chars

# Optional: enables tier-1 Claude with prompt caching
ANTHROPIC_API_KEY=sk-ant-...
```

First run: ~10 min (image pull). Processing time: ~15 sec/document.

---

## Service URLs

| Service | URL | Default credentials |
|---|---|---|
| App | http://localhost:5173 | register any account |
| API docs | http://localhost:8000/docs | — |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3001 | admin / clauseguard |
| MLflow | http://localhost:5000 | — |
| Flower (Celery) | http://localhost:5555 | admin / clauseguard |
| MinIO | http://localhost:9001 | minio / minio123 |

---

## ML Training & Evaluation

```bash
cd backend

# Fine-tune Legal-BERT on CUAD
python scripts/train_legal_bert.py --epochs 3 --output ./checkpoints/cuad

# Benchmark evaluation (CUAD test set)
python scripts/evaluate_cuad.py --sample 500

# Use fine-tuned model
export CUAD_MODEL_PATH=./checkpoints/cuad/best
```

---

## Tests

```bash
cd backend
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## API Reference

```
POST  /api/v1/documents/upload           Upload PDF/DOCX
GET   /api/v1/documents/{id}/clauses     All extracted clauses
POST  /api/v1/chat/{id}/stream           Streaming AI chat (SSE)
POST  /api/v1/negotiate/{id}             Negotiation advice
GET   /api/v1/obligations/{id}           Deadline extraction
POST  /api/v1/compare                    Clause-level document diff
POST  /api/v1/search                     Cross-document semantic search
GET   /api/v1/analytics/summary          Portfolio KPIs
GET   /api/v1/analytics/risk-distribution  Clause risk breakdown
GET   /api/v1/analytics/category-heatmap   Category frequency + risk
GET   /api/v1/analytics/trends           Risk score trend (30 days)
GET   /api/v1/analytics/benchmark/{id}   Industry benchmark comparison
GET   /api/v1/analytics/audit-log        User audit trail
POST  /api/v1/batch/analyze              Parallel multi-document analysis
WS    /ws/document/{id}?token=...        Real-time processing status
GET   /metrics                           Prometheus metrics
GET   /readiness                         Kubernetes readiness probe
```

---

## Stack

**Backend**: Python 3.11 · FastAPI · SQLAlchemy · Alembic · Celery · Redis  
**ML**: Legal-BERT · FAISS · sentence-transformers · spaCy · transformers · MLflow  
**LLM**: Anthropic Claude (prompt caching) · Groq Llama 3.3 70B · HuggingFace  
**Frontend**: React 18 · Vite · Tailwind CSS · Recharts · Framer Motion  
**Infra**: PostgreSQL 16 · Redis 7 · MinIO · Prometheus · Grafana · Docker Compose  
**CI/CD**: GitHub Actions — lint · typecheck · test · ML eval · Docker · security scan

---

## Chrome Extension

1. `chrome://extensions` → Enable **Developer mode**
2. **Load unpacked** → select `extension/`
3. Visit any Terms of Service page → click **Analyze**

---

## License

MIT
