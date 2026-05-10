# ClauseGuard

AI-powered contract risk analyzer. Upload any PDF or DOCX, get a clause-by-clause risk breakdown, ask questions in plain English, and know exactly what to negotiate before you sign.

> Built for individuals — not enterprise legal teams.

---

## What it does

- **Risk scoring** — classifies every clause into 41 categories with a 0–100 risk score
- **Plain English** — AI explains each clause in simple language
- **AI Chat** — ask anything about your contract, get streaming answers
- **Negotiate** — generates fairer alternative clause language you can actually use
- **Obligations timeline** — extracts every deadline, payment date, and notice period
- **Compare** — clause-level diff between two contract versions
- **Sign** — digital signature with SHA-256 audit trail and signed PDF export
- **Chrome extension** — analyze any Terms of Service page inline

---

## Stack

`FastAPI` · `React 18` · `PostgreSQL` · `Redis` · `Celery` · `spaCy` · `Groq Llama 3.3 70B` · `Docker`

---

## Quick start

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop) and a free [Groq API key](https://console.groq.com).

```bash
git clone https://github.com/YOUR_USERNAME/clauseguard.git
cd clauseguard

# Add your Groq key
cp .env.example .env     # then edit GROQ_API_KEY in .env

docker compose up -d
```

Open **http://localhost:5173** — or click **Try the demo** on the landing page, no sign-up needed.

> First run takes ~10 min (downloads all images). After that, ~15 seconds.

---

## Environment

Only one variable is required to get started:

| Variable | Required | Notes |
|---|---|---|
| `GROQ_API_KEY` | Yes | Free at [console.groq.com](https://console.groq.com) |
| `JWT_SECRET` | Yes | Any long random string |
| `DATABASE_URL` | Auto | Set by Docker Compose |
| `REDIS_URL` | Auto | Set by Docker Compose |

---

## API

Interactive docs at `http://localhost:8000/docs`

```
POST  /api/v1/auth/register
POST  /api/v1/auth/login
POST  /api/v1/documents/upload
GET   /api/v1/documents/{id}/clauses
POST  /api/v1/chat/{id}/stream          # SSE streaming
GET   /api/v1/obligations/{id}          # extracted deadlines
POST  /api/v1/negotiate/{id}            # AI negotiation advice
POST  /api/v1/compare
POST  /api/v1/sign/{id}
```

---

## Chrome extension

1. Go to `chrome://extensions` → enable **Developer mode**
2. **Load unpacked** → select the `extension/` folder
3. Visit any Terms of Service or Privacy Policy page
4. Click the floating **Analyze** button

---

## Docker

```bash
docker compose up -d        # start
docker compose stop         # stop (keeps data)
docker compose down -v      # full reset
docker compose logs -f backend
```

---

## License

MIT
