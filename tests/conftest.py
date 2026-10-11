"""Shared test setup.

Every test starts from the same seeded world, so a test can never be
contaminated by whatever the test before it wrote.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

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
