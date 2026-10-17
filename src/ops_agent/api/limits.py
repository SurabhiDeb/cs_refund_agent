"""Per key rate limiting.

Every /chat call spends money at the gateway, so an unlimited key is an
unlimited bill. The limit is per key rather than per IP, because the key is
the thing that costs something.

A fixed window, not a sliding one. It is cruder, but it is one Redis round
trip and it cannot disagree with itself.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Generator
from contextlib import contextmanager

from fastapi import HTTPException
from redis import Redis

from ops_agent.config import settings
from ops_agent.obs.metrics import SHED

_redis = Redis.from_url(settings.redis_url)


def enforce(api_key: str, *, limit: int, window_seconds: int) -> None:
    """Count this call. Raise 429 once the window's allowance is gone."""
    # The key is hashed before it reaches Redis. Redis is not a secret store.
    bucket = "rl:" + hashlib.sha256(api_key.encode()).hexdigest()[:32]

    count = _redis.incr(bucket)
    if count == 1:
        # First call in this window, so start the clock.
        _redis.expire(bucket, window_seconds)

    if int(count) > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit reached, {limit} requests per {window_seconds}s.",
        )


def redis_ok() -> bool:
    """Used by /health. A dead Redis means no rate limiting, so the service
    is degraded even though it could still answer."""
    try:
        return bool(_redis.ping())
    except Exception:
        return False


# One semaphore per process. Granian runs sync endpoints in a thread pool,
# so what this bounds is threads, and the ceiling is per worker.
_inflight = threading.BoundedSemaphore(settings.max_concurrent_chats)


@contextmanager
def bounded_concurrency() -> Generator[None]:
    """Shed load rather than queue it.

    Beat 13.1 measured throughput falling as load rose past ten concurrent
    callers: the service got slower and did less work at the same time.
    Queueing is what turns overload into a five second pool timeout and a
    500. A caller we cannot serve is better told so immediately.

    This is separate from the rate limit, which is per key. Ten keys at ten
    requests each walk straight past that and arrive here.
    """
    if not _inflight.acquire(blocking=False):
        SHED.inc()
        raise HTTPException(
            status_code=503,
            detail="The service is at capacity. Retry shortly.",
            headers={"Retry-After": "1"},
        )
    try:
        yield
    finally:
        _inflight.release()
