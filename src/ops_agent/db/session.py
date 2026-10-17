"""One place that knows how to connect to the database.

The engine is built on first use, not on import. Testcontainers invents a
database at runtime, so the URL is not known when this module is imported.
That also means importing anything in db/ no longer needs a live database.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from ops_agent.config import settings

load_dotenv()


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """One engine per process, built the first time something asks for it."""
    return create_engine(
        os.environ["DATABASE_URL"],
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        # A connection idle through a Postgres restart is dead and still
        # looks fine. One round trip on checkout is cheaper than the 500
        # it prevents.
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def reset_engine() -> None:
    """Forget the cached engine.

    Only the test harness calls this, after pointing DATABASE_URL at a fresh
    container. Without it the first container's engine is reused forever.
    """
    get_session_factory.cache_clear()
    get_engine.cache_clear()


@contextmanager
def session_scope() -> Generator[Session]:
    """One transaction. Commits on success, rolls back on any exception."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
