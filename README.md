<div align="center">

# ClauseGuard

**AI-powered legal document risk analyzer for everyone.**

ClauseGuard reads your contracts, scores every clause for risk, explains them in plain English, and tells you exactly what to negotiate — so you never sign blind again.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)](https://docs.docker.com/compose)
[![Groq](https://img.shields.io/badge/Groq-Llama%203.3%2070B-orange?style=flat-square)](https://console.groq.com)

</div>

---

## Why ClauseGuard?

Enterprise legal tools like iCertis and Krista AI require contact-sales demos, lock you into annual contracts, and are built for legal teams — not individuals. ClauseGuard is:

- **For everyone** — freelancers, employees, students, anyone who signs a contract
- **Free and open source** — self-hosted, no hidden fees, no vendor lock-in
- **Actually actionable** — doesn't just flag risks, tells you how to negotiate them
- **Conversational** — ask any question about your contract in natural language

---

## Features

| Feature | Description |
|---|---|
| **Risk Analysis** | Classifies every clause into 41 CUAD-style categories with risk scores 0–100 |
| **Plain English** | AI-generated summary for each clause using Groq Llama 3.3 70B |
| **⚡ Negotiate This Clause** | Generates fairer alternative clause language + negotiation tips |
| **Obligations Timeline** | Extracts all deadlines, payments, renewal windows, and notice periods |
| **Contract Type Detection** | Auto-detects NDA, Employment, SaaS, Freelance, Rental agreements |
| **AI Chat** | Ask anything — streaming answers with HyDE retrieval + multi-query expansion |
| **Document Compare** | Clause-level diff between two contract versions |
| **Digital Signature** | Canvas signature pad with SHA-256 audit trail + signed PDF export |
| **Chrome Extension** | Analyze any Terms of Service or Privacy Policy page inline |

---

## Demo

```
Email:    demo@clauseguard.ai
Password: ClauseGuard123!
```

Or click **"Try the demo"** on the landing page — no sign-up required.

---

## Quick Start

**Requirements:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) and a free [Groq API key](https://console.groq.com).

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/clauseguard.git
cd clauseguard

# 2. Configure environment
cp .env.example .env
# Edit .env and set: GROQ_API_KEY=gsk_your_key_here

# 3. Start all services
docker compose up -d

# 4. Open the app
open http://localhost:5173
```

First run takes ~10 minutes (downloads Python, Node, PostgreSQL, Redis images). Subsequent starts take ~15 seconds.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, Tailwind CSS, Recharts, Framer Motion, PDF.js |
| **Backend** | FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic |
| **AI / NLP** | spaCy (en_core_web_sm), Groq Llama 3.3 70B, HuggingFace Mistral 7B |
| **RAG Pipeline** | HyDE + Multi-query expansion + Reciprocal Rank Fusion |
| **Task Queue** | Celery + Redis |
| **Database** | PostgreSQL 16 |
| **Auth** | JWT (access + refresh tokens), bcrypt |
| **Infrastructure** | Docker, Docker Compose |
| **Extension** | Chrome Manifest V3 |

---

## Architecture

```
Browser (React + Vite)          Chrome Extension (MV3)
        │                               │
        ▼ JWT Bearer                    ▼ POST
┌─────────────────────────────────────────────────┐
│            FastAPI  (Port 8000)                 │
│  /auth  /documents  /chat  /negotiate           │
│  /obligations  /compare  /sign  /extension      │
└──────────────────────┬──────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   PostgreSQL       Redis         Celery Worker
   (Port 5432)   (Port 6379)   document pipeline
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼             ▼
                     spaCy NLP   Classifier    Groq LLM
                    segmenter    (41 CUAD)   explainer
```

---

## Document Processing Pipeline

```
Upload PDF / DOCX
    ↓ Extract text (PyMuPDF / python-docx)
    ↓ Segment into clauses (spaCy en_core_web_sm)
    ↓ Classify each clause (41-category keyword engine)
    ↓ Score risk per clause (weighted scoring, 0–100)
    ↓ Generate plain-English explanation (Groq → HuggingFace → template)
    ↓ Store in PostgreSQL
    ↓ Frontend auto-polls → displays results (no refresh needed)
```

---

## AI Chat Pipeline

```
User question
    ↓ HyDE: generate hypothetical legal clause text → embed → search
    ↓ Multi-query: expand into 3 sub-queries → search all → Reciprocal Rank Fusion
    ↓ Always include: all critical + high risk clauses
    ↓ Build focused context (top 14 relevant clauses)
    ↓ Groq Llama 3.3 70B streams answer token by token
    ↓ Generate 3 follow-up question suggestions
```

---

## Project Structure

```
clauseguard/
├── backend/
│   ├── app/
│   │   ├── api/          # REST endpoints (auth, chat, documents, negotiate, ...)
│   │   ├── core/         # Config, database, security (JWT)
│   │   ├── ml/           # NLP pipeline (segmenter, classifier, scorer, explainer)
│   │   ├── models/       # SQLAlchemy ORM + Pydantic schemas
│   │   ├── tasks/        # Celery document processing task
│   │   └── main.py       # FastAPI app entry point
│   ├── mcp_server.py     # MCP server for Claude Desktop integration
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/          # Axios client + API functions
│   │   ├── components/   # ClauseCard, ChatPanel, NegotiatePanel, ObligationsTimeline, ...
│   │   ├── hooks/        # useDocuments (polling)
│   │   └── pages/        # Dashboard, Upload, Analysis, Compare, Sign, Auth
│   ├── Dockerfile
│   └── package.json
├── extension/            # Chrome Manifest V3 extension
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | **Yes** | Free at [console.groq.com](https://console.groq.com) (no credit card) |
| `JWT_SECRET` | **Yes** | Any long random string |
| `DATABASE_URL` | Auto | Set automatically in Docker |
| `REDIS_URL` | Auto | Set automatically in Docker |
| `HUGGINGFACE_API_KEY` | Optional | For HF fallback LLM |
| `MAX_UPLOAD_MB` | Optional | Default: 50 |
| `ENABLE_DEMO_SEED` | Optional | Default: true |

---

## API Reference

Interactive docs at **http://localhost:8000/docs** after starting the app.

Key endpoints:

```
POST /api/v1/auth/register          Create account
POST /api/v1/auth/login             Login → JWT tokens
POST /api/v1/documents/upload       Upload PDF or DOCX
GET  /api/v1/documents/{id}/clauses All extracted clauses
POST /api/v1/chat/{id}/stream       Streaming AI chat (SSE)
GET  /api/v1/obligations/{id}       Extracted deadlines & obligations
POST /api/v1/negotiate/{id}         AI negotiation advice for a clause
POST /api/v1/compare                Clause-level document diff
POST /api/v1/sign/{id}              Sign with audit trail
POST /api/v1/extension/analyze-text Chrome extension endpoint
```

---

## Chrome Extension

1. Open `chrome://extensions` → enable **Developer mode**
2. Click **Load unpacked** → select the `extension/` folder
3. Navigate to any Terms of Service, Privacy Policy, or legal page
4. Click the floating **"Analyze with ClauseGuard"** button

---

## MCP Server (Claude Desktop)

ClauseGuard includes an MCP server for [Claude Desktop](https://claude.ai/download) integration:

```bash
pip install mcp
python backend/mcp_server.py
```

Add to `~/.claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "clauseguard": {
      "command": "python",
      "args": ["/path/to/backend/mcp_server.py"],
      "env": { "DATABASE_URL": "postgresql://clauseguard:clauseguard@localhost:5432/clauseguard" }
    }
  }
}
```

---

## Docker Commands

```bash
docker compose up -d          # Start all services
docker compose stop           # Stop (data preserved)
docker compose down           # Remove containers (data preserved)
docker compose down -v        # Full reset including database
docker compose logs -f backend # Live logs
```

---

## License

MIT — free to use, modify, and distribute.

---

<div align="center">
Built with FastAPI · React · PostgreSQL · Groq · Docker
</div>
