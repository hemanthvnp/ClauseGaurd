"""
Prometheus Metrics
==================
Instruments ClauseGuard with production-grade observability.

Exposes /metrics endpoint (Prometheus text format).
FastAPI middleware records latency + status for every request.

Metrics exported:
  clauseguard_http_requests_total          counter  {method, endpoint, status}
  clauseguard_http_request_duration_seconds histogram {method, endpoint}
  clauseguard_documents_processed_total    counter  {status}
  clauseguard_ml_inference_seconds         histogram {model}
  clauseguard_active_websocket_connections gauge
  clauseguard_cache_operations_total       counter  {operation, result}

Usage:
    from app.core.metrics import (
        record_document_processed, record_ml_inference,
        inc_websocket_connections, dec_websocket_connections,
        record_cache_op,
    )
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

try:
    from prometheus_client import (  # type: ignore[import]
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    _PROM_OK = True
except ImportError:
    _PROM_OK = False

# ── Metric definitions ────────────────────────────────────────────────────────

if _PROM_OK:
    _HTTP_REQUESTS = Counter(
        "clauseguard_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )
    _HTTP_DURATION = Histogram(
        "clauseguard_http_request_duration_seconds",
        "HTTP request latency",
        ["method", "endpoint"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )
    _DOCS_PROCESSED = Counter(
        "clauseguard_documents_processed_total",
        "Documents processed",
        ["status"],
    )
    _ML_INFERENCE = Histogram(
        "clauseguard_ml_inference_seconds",
        "ML model inference latency",
        ["model"],
        buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
    )
    _WS_CONNECTIONS = Gauge(
        "clauseguard_active_websocket_connections",
        "Active WebSocket connections",
    )
    _CACHE_OPS = Counter(
        "clauseguard_cache_operations_total",
        "Cache hit/miss/set",
        ["operation", "result"],
    )
else:
    # Stub objects so imports don't break when prometheus_client not installed
    class _NoOpCounter:
        def labels(self, **_): return self
        def inc(self, *_): pass

    class _NoOpHistogram:
        def labels(self, **_): return self
        def observe(self, *_): pass
        def time(self): return _NoopCtx()

    class _NoOpGauge:
        def inc(self, *_): pass
        def dec(self, *_): pass
        def set(self, *_): pass

    class _NoopCtx:
        def __enter__(self): return self
        def __exit__(self, *_): pass

    _HTTP_REQUESTS = _NoOpCounter()  # type: ignore[assignment]
    _HTTP_DURATION = _NoOpHistogram()  # type: ignore[assignment]
    _DOCS_PROCESSED = _NoOpCounter()  # type: ignore[assignment]
    _ML_INFERENCE = _NoOpHistogram()  # type: ignore[assignment]
    _WS_CONNECTIONS = _NoOpGauge()  # type: ignore[assignment]
    _CACHE_OPS = _NoOpCounter()  # type: ignore[assignment]


# ── FastAPI middleware ─────────────────────────────────────────────────────────

async def metrics_middleware(request: Request, call_next: Callable) -> Response:
    start = time.perf_counter()

    # Normalise path: strip UUIDs for cardinality control
    path = request.url.path
    for segment in path.split("/"):
        if len(segment) == 36 and segment.count("-") == 4:
            path = path.replace(segment, "{id}")
            break

    response = await call_next(request)
    duration = time.perf_counter() - start

    _HTTP_REQUESTS.labels(
        method=request.method,
        endpoint=path,
        status=str(response.status_code),
    ).inc()
    _HTTP_DURATION.labels(method=request.method, endpoint=path).observe(duration)

    return response


def metrics_endpoint() -> Response:
    if not _PROM_OK:
        return PlainTextResponse("prometheus_client not installed", status_code=503)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Helper functions (call these from business logic) ─────────────────────────

def record_document_processed(status: str = "complete") -> None:
    _DOCS_PROCESSED.labels(status=status).inc()


@contextmanager
def time_ml_inference(model: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        _ML_INFERENCE.labels(model=model).observe(time.perf_counter() - start)


def inc_websocket_connections() -> None:
    _WS_CONNECTIONS.inc()


def dec_websocket_connections() -> None:
    _WS_CONNECTIONS.dec()


def record_cache_op(operation: str, result: str) -> None:
    _CACHE_OPS.labels(operation=operation, result=result).inc()


def register_metrics(app: FastAPI) -> None:
    """Wire middleware and /metrics endpoint into a FastAPI app."""
    app.middleware("http")(metrics_middleware)
    app.add_route("/metrics", lambda req: metrics_endpoint())
