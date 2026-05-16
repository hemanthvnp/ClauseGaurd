"""
Redis Token-Bucket Rate Limiter
=================================
Per-user, per-endpoint rate limiting using the token bucket algorithm.
Falls back to an in-memory store when Redis is unavailable.

Algorithm:
  - Each user×endpoint bucket holds `capacity` tokens.
  - Tokens refill at `rate` tokens/second.
  - Each request consumes 1 token. If the bucket is empty → HTTP 429.
  - State is stored in Redis with a TTL, so buckets expire naturally.

Usage (FastAPI dependency injection):
    @router.post("/upload")
    def upload(
        _: None = Depends(RateLimiter(requests_per_minute=10)),
        current_user: User = Depends(get_current_user),
    ):
        ...

    # Or with a pre-built instance:
    upload_limiter = RateLimiter(requests_per_minute=10)

    @router.post("/upload")
    def upload(_: None = Depends(upload_limiter)):
        ...
"""
from __future__ import annotations

import time
import threading
from collections import defaultdict
from typing import Callable

from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.core.security import get_current_user
from app.models.schema import User

try:
    import redis as _redis_mod
    _REDIS_OK = True
except ImportError:
    _REDIS_OK = False

settings = get_settings()

# ── In-memory fallback ────────────────────────────────────────────────────────

_mem_lock = threading.Lock()
_mem_buckets: dict[str, tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))


def _mem_consume(key: str, capacity: float, rate: float) -> bool:
    """Returns True if token consumed, False if rate limit exceeded."""
    with _mem_lock:
        now = time.monotonic()
        tokens, last_refill = _mem_buckets[key]
        elapsed = now - last_refill if last_refill else 0.0
        tokens = min(capacity, tokens + elapsed * rate)
        if tokens < 1.0:
            _mem_buckets[key] = (tokens, now)
            return False
        _mem_buckets[key] = (tokens - 1.0, now)
        return True


# ── Redis implementation (Lua script for atomicity) ──────────────────────────

_LUA_TOKEN_BUCKET = """
local key      = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate     = tonumber(ARGV[2])
local now      = tonumber(ARGV[3])
local ttl      = tonumber(ARGV[4])

local data     = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens   = tonumber(data[1]) or capacity
local last_r   = tonumber(data[2]) or now

local elapsed  = now - last_r
tokens = math.min(capacity, tokens + elapsed * rate)

if tokens < 1.0 then
    redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, ttl)
    return 0
end

tokens = tokens - 1.0
redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, ttl)
return 1
"""


class _RedisBackend:
    def __init__(self) -> None:
        self._client = None
        self._script = None
        self._init()

    def _init(self) -> None:
        if not _REDIS_OK:
            return
        try:
            client = _redis_mod.Redis.from_url(settings.redis_url, decode_responses=False)
            client.ping()
            self._client = client
            self._script = client.register_script(_LUA_TOKEN_BUCKET)
        except Exception:
            self._client = None

    def consume(self, key: str, capacity: float, rate: float, ttl: int = 120) -> bool:
        if self._client is None or self._script is None:
            return _mem_consume(key, capacity, rate)
        try:
            now = time.time()
            result = self._script(keys=[key], args=[capacity, rate, now, ttl])
            return bool(result)
        except Exception:
            return _mem_consume(key, capacity, rate)


_redis_backend = _RedisBackend()


# ── Public API ────────────────────────────────────────────────────────────────

class RateLimiter:
    """
    FastAPI dependency that enforces token-bucket rate limiting per user.

    Args:
        requests_per_minute: sustained allowed request rate
        burst:               max burst (defaults to 2× rpm, capped at 100)
        scope:               namespace prefix for Redis key (default "global")
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst: int | None = None,
        scope: str = "global",
    ) -> None:
        self._rpm = requests_per_minute
        self._rate = requests_per_minute / 60.0
        self._capacity = float(burst or min(requests_per_minute * 2, 100))
        self._scope = scope

    def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> None:
        user_id = str(current_user.id)
        key = f"rl:{self._scope}:{user_id}"
        allowed = _redis_backend.consume(key, self._capacity, self._rate)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {self._rpm} requests/minute.",
                headers={"Retry-After": str(int(60 / self._rate))},
            )


# ── Pre-built limiters (import and use directly) ──────────────────────────────

upload_limiter   = RateLimiter(requests_per_minute=10,  burst=15, scope="upload")
chat_limiter     = RateLimiter(requests_per_minute=30,  burst=40, scope="chat")
default_limiter  = RateLimiter(requests_per_minute=60,  burst=80, scope="default")
batch_limiter    = RateLimiter(requests_per_minute=5,   burst=5,  scope="batch")
