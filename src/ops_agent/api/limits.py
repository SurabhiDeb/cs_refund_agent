"""Per key rate limiting.

Every /chat call spends money at the gateway, so an unlimited key is an
unlimited bill. The limit is per key rather than per IP, because the key is
the thing that costs something.

A fixed window, not a sliding one. It is cruder, but it is one Redis round
trip and it cannot disagree with itself.
"""

from __future__ import annotations

import hashlib

from fastapi import HTTPException
from redis import Redis

from ops_agent.config import settings

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
