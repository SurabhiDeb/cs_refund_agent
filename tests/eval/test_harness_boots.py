"""Proves the container, the migration, and the seed all work together."""

from __future__ import annotations

from sqlalchemy import func, select

from ops_agent.db.models import Order
from ops_agent.db.session import session_scope


def test_the_seeded_world_arrives(fresh_db: None) -> None:
    with session_scope() as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 67
