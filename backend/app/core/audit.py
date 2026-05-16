"""
Structured Audit Logging
=========================
Records every significant user action as a structured audit event.
Critical for finance / regulated-industry deployments (SOC 2, SOX, GDPR).

Events are stored in the `audit_events` PostgreSQL table AND emitted as
structured JSON to stdout (so log aggregation pipelines like ELK / Splunk
can ingest them without DB access).

Schema:
  id           UUID     primary key
  user_id      UUID     FK → users
  action       str      e.g. "document.upload"
  resource_id  str|None
  metadata     JSON
  ip_address   str|None
  user_agent   str|None
  created_at   datetime

Actions catalogue:
  auth.login          auth.logout           auth.register
  document.upload     document.delete       document.view
  document.analyze    document.download
  chat.query          negotiate.request
  search.query        batch.submit
  signature.create
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session

from app.core.database import Base

logger = logging.getLogger("clauseguard.audit")


# ── ORM model ─────────────────────────────────────────────────────────────────

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id          = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id     = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    action      = Column(String(80), nullable=False, index=True)
    resource_id = Column(String(120), nullable=True)
    metadata_   = Column("metadata", Text, nullable=True)
    ip_address  = Column(String(45), nullable=True)
    user_agent  = Column(String(256), nullable=True)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":          str(self.id),
            "user_id":     str(self.user_id) if self.user_id else None,
            "action":      self.action,
            "resource_id": self.resource_id,
            "metadata":    json.loads(self.metadata_) if self.metadata_ else {},
            "ip_address":  self.ip_address,
            "user_agent":  self.user_agent,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
        }


# ── Public helper ──────────────────────────────────────────────────────────────

def log_event(
    db: Session,
    *,
    action: str,
    user_id: UUID | str | None = None,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditEvent:
    """
    Persist an audit event and emit it as structured JSON to stdout.

    Args:
        db:          SQLAlchemy session (caller manages commit)
        action:      dot-namespaced action string e.g. "document.upload"
        user_id:     the acting user (None for unauthenticated events)
        resource_id: affected resource (document id, clause id, etc.)
        metadata:    arbitrary key-value context (sanitised; no PII)
        ip_address:  request remote host
        user_agent:  HTTP User-Agent header
    """
    event = AuditEvent(
        user_id     = UUID(str(user_id)) if user_id else None,
        action      = action[:80],
        resource_id = str(resource_id)[:120] if resource_id else None,
        metadata_   = json.dumps(metadata or {}),
        ip_address  = (ip_address or "")[:45],
        user_agent  = (user_agent or "")[:256],
    )
    try:
        db.add(event)
        db.flush()  # get ID without committing
    except Exception as exc:
        logger.error("audit DB write failed: %s", exc)
        db.rollback()

    # Structured JSON log — picked up by any log aggregator
    record = {
        "audit":       True,
        "action":      action,
        "user_id":     str(user_id) if user_id else None,
        "resource_id": str(resource_id) if resource_id else None,
        "ip":          ip_address,
        "ts":          datetime.now(timezone.utc).isoformat(),
        **(metadata or {}),
    }
    print(json.dumps(record), file=sys.stdout, flush=True)
    return event


def get_user_audit_log(
    db: Session,
    user_id: UUID,
    *,
    action_prefix: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve paginated audit log for a specific user."""
    from sqlalchemy import select

    q = select(AuditEvent).where(AuditEvent.user_id == user_id)
    if action_prefix:
        q = q.where(AuditEvent.action.startswith(action_prefix))
    q = q.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)
    return [e.to_dict() for e in db.scalars(q).all()]
