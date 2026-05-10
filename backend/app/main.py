from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.demo import router as demo_router
from app.api.compare import router as compare_router
from app.api.documents import router as documents_router
from app.api.extension import router as extension_router
from app.api.negotiate import router as negotiate_router
from app.api.obligations import router as obligations_router
from app.api.sign import router as sign_router
from app.core.config import get_settings
from app.core.database import Base, engine
from app.models import schema  # noqa: F401 - ensure ORM models are imported
from app.seed import seed_demo_data

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    Base.metadata.create_all(bind=engine)
    if getattr(settings, 'enable_demo_seed', True):
        seed_demo_data()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(demo_router, prefix=settings.api_v1_prefix)
app.include_router(documents_router, prefix=settings.api_v1_prefix)
app.include_router(compare_router, prefix=settings.api_v1_prefix)
app.include_router(sign_router, prefix=settings.api_v1_prefix)
app.include_router(extension_router, prefix=settings.api_v1_prefix)
app.include_router(chat_router, prefix=settings.api_v1_prefix)
app.include_router(negotiate_router, prefix=settings.api_v1_prefix)
app.include_router(obligations_router, prefix=settings.api_v1_prefix)


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}
