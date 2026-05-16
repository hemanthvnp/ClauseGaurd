"""
WebSocket — Real-Time Document Processing Status
=================================================
Clients subscribe to a document's processing progress via WebSocket.
The Celery worker publishes progress events to Redis pub/sub;
this gateway subscribes and forwards to connected browsers.

Connection lifecycle:
  1. Browser → WS /ws/document/{document_id}  (JWT token in query param)
  2. Gateway authenticates token, validates document ownership
  3. Gateway subscribes to Redis channel  clauseguard:doc:{document_id}
  4. Worker publishes events:  {"stage": "segmenting", "pct": 20}
  5. Gateway forwards JSON to the browser
  6. On "complete" or "failed", gateway closes the connection

Redis pub/sub channel format:
  channel : clauseguard:doc:{document_id}
  message : JSON string {"stage": str, "pct": int, "detail": str|null}
"""
from __future__ import annotations

import asyncio
import json
import sys
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.metrics import dec_websocket_connections, inc_websocket_connections
from app.core.security import decode_access_token
from app.models.schema import Document

router = APIRouter(tags=["websocket"])
settings = get_settings()

_TERMINAL_STAGES = {"complete", "failed"}
_POLL_INTERVAL_S = 0.5   # seconds between Redis poll checks


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/document/{document_id}")
async def document_status_ws(
    websocket: WebSocket,
    document_id: UUID,
    token: str = Query(..., description="JWT access token"),
) -> None:
    """
    Stream processing progress for a document.

    Authentication: pass the JWT access token as ?token=<jwt>.
    Events: {"stage": str, "pct": int, "detail": str|null}
    Terminal: {"stage": "complete"|"failed", "pct": 100, "detail": null}
    """
    await websocket.accept()
    inc_websocket_connections()

    try:
        # Authenticate
        user_id = _authenticate(token)
        if user_id is None:
            await _close(websocket, 4001, "Invalid or expired token")
            return

        # Validate document ownership
        db: Session = SessionLocal()
        try:
            doc = db.get(Document, document_id)
            if doc is None or str(doc.user_id) != user_id:
                await _close(websocket, 4004, "Document not found")
                return
            # Already done?
            if doc.status in _TERMINAL_STAGES:
                await websocket.send_json({
                    "stage": doc.status,
                    "pct": 100,
                    "detail": f"Document {doc.status}",
                })
                return
        finally:
            db.close()

        # Subscribe to Redis pub/sub
        await _redis_subscribe(websocket, document_id)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"[ws] error: {exc}", file=sys.stderr)
    finally:
        dec_websocket_connections()


# ── Redis pub/sub subscription ────────────────────────────────────────────────

async def _redis_subscribe(websocket: WebSocket, document_id: UUID) -> None:
    channel = f"clauseguard:doc:{document_id}"
    try:
        import redis.asyncio as aioredis  # type: ignore[import]
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                event = json.loads(message["data"])
                await websocket.send_json(event)
                if event.get("stage") in _TERMINAL_STAGES:
                    break
            except Exception:
                pass

        await pubsub.unsubscribe(channel)
        await client.aclose()
    except ImportError:
        # redis.asyncio not available — fall back to polling
        await _polling_fallback(websocket, document_id)
    except Exception as exc:
        print(f"[ws] redis subscribe error: {exc}", file=sys.stderr)
        await _polling_fallback(websocket, document_id)


async def _polling_fallback(websocket: WebSocket, document_id: UUID) -> None:
    """Poll the database every 500 ms when Redis pub/sub is unavailable."""
    stages = ["queued", "extracting", "segmenting", "classifying", "scoring", "explaining"]
    stage_idx = 0
    for _ in range(120):  # max 60 seconds
        await asyncio.sleep(_POLL_INTERVAL_S)
        db: Session = SessionLocal()
        try:
            doc = db.get(Document, document_id)
            if doc is None:
                break
            if doc.status in _TERMINAL_STAGES:
                await websocket.send_json({
                    "stage": doc.status, "pct": 100, "detail": None
                })
                break
            # Simulate stage progression for better UX
            stage_idx = min(stage_idx + 1, len(stages) - 1)
            pct = int((stage_idx + 1) / len(stages) * 90)
            await websocket.send_json({
                "stage": stages[stage_idx], "pct": pct, "detail": None
            })
        finally:
            db.close()


# ── Publisher (called from Celery worker) ─────────────────────────────────────

def publish_progress(document_id: str, stage: str, pct: int, detail: str | None = None) -> None:
    """
    Publish a processing progress event from the Celery worker.
    Call this at key stages in document_processor.process_document().
    """
    try:
        import redis as _redis  # type: ignore[import]
        client = _redis.Redis.from_url(settings.redis_url, decode_responses=True)
        channel = f"clauseguard:doc:{document_id}"
        payload = json.dumps({"stage": stage, "pct": pct, "detail": detail})
        client.publish(channel, payload)
        client.close()
    except Exception as exc:
        print(f"[ws] publish_progress error: {exc}", file=sys.stderr)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _authenticate(token: str) -> str | None:
    try:
        payload = decode_access_token(token)
        return payload.get("sub")
    except Exception:
        return None


async def _close(websocket: WebSocket, code: int, reason: str) -> None:
    try:
        await websocket.send_json({"error": reason})
        await websocket.close(code=code)
    except Exception:
        pass
