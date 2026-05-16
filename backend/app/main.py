from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.batch import router as batch_router
from app.api.chat import router as chat_router
from app.api.compare import router as compare_router
from app.api.demo import router as demo_router
from app.api.documents import router as documents_router
from app.api.extension import router as extension_router
from app.api.negotiate import router as negotiate_router
from app.api.obligations import router as obligations_router
from app.api.search import router as search_router
from app.api.sign import router as sign_router
from app.api.ws import router as ws_router
from app.core.audit import AuditEvent
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.metrics import register_metrics
from app.models import schema  # noqa: F401 — ensure ORM models are imported
from app.seed import seed_demo_data

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    Base.metadata.create_all(bind=engine)
    if getattr(settings, "enable_demo_seed", True):
        seed_demo_data()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "ClauseGuard — AI-powered legal document risk analyzer. "
        "41-category clause classification, FAISS semantic search, "
        "real-time WebSocket updates, and portfolio-level risk analytics."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics (exposes /metrics endpoint + request instrumentation)
register_metrics(app)

# ── Routes ────────────────────────────────────────────────────────────────────

_V1 = settings.api_v1_prefix

app.include_router(auth_router,      prefix=_V1)
app.include_router(demo_router,      prefix=_V1)
app.include_router(documents_router, prefix=_V1)
app.include_router(compare_router,   prefix=_V1)
app.include_router(sign_router,      prefix=_V1)
app.include_router(extension_router, prefix=_V1)
app.include_router(chat_router,      prefix=_V1)
app.include_router(negotiate_router, prefix=_V1)
app.include_router(obligations_router, prefix=_V1)

# ── New v2 routes ─────────────────────────────────────────────────────────────
app.include_router(analytics_router, prefix=_V1)
app.include_router(search_router,    prefix=_V1)
app.include_router(batch_router,     prefix=_V1)

# WebSocket (no API prefix — browsers connect directly)
app.include_router(ws_router)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": "2.0.0"}


@app.get("/readiness", tags=["system"])
def readiness() -> dict[str, str]:
    """Kubernetes readiness probe — checks DB connectivity."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"DB not ready: {exc}")
