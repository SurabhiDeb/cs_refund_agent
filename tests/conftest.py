"""Shared test setup.

Every test starts from the same seeded world, so a test can never be
contaminated by whatever the test before it wrote.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from redis import Redis
from sqlalchemy.orm import Session

from ops_agent.config import settings
from ops_agent.db.seed import seed
from ops_agent.db.session import session_scope
from ops_agent.tools.context import ToolContext


@pytest.fixture
def db() -> Generator[Session]:
    seed()
    with session_scope() as session:
        yield session


@pytest.fixture
def owner() -> ToolContext:
    """The normal caller, allowed to write."""
    return ToolContext(customer_id="cus_001", write_enabled=True)


@pytest.fixture
def owner_readonly() -> ToolContext:
    """The same caller with the kill switch thrown."""
    return ToolContext(customer_id="cus_001", write_enabled=False)


@pytest.fixture(autouse=True)
def clear_rate_limits() -> None:
    """Every test starts with a full allowance.

    The limiter is a fixed window in Redis, shared by every test in the
    session. Without this, whichever test happens to run eleventh gets a
    429 for calls another test spent. That looks like a flake and is not.

    Tolerant of a dead Redis, because the eval tests need Postgres only.
    """
    try:
        redis = Redis.from_url(settings.redis_url)
        for key in redis.scan_iter("rl:*"):
            redis.delete(key)
    except Exception:
        pass
