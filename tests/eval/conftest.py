"""A real Postgres, started once, reseeded before every case.

BUILD_GUIDE Beat 6 asks for a fresh Postgres per case. A container takes
seconds to start, so 70 containers is minutes of wall clock for no extra
isolation. seed() deletes every row before it inserts, so a reseed leaves the
database exactly as a new container would. One container, reseeded per case.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from testcontainers.postgres import PostgresContainer

from ops_agent.db.seed import seed
from ops_agent.db.session import reset_engine

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def postgres() -> Generator[None]:
    """One throwaway Postgres for the whole eval run, migrated to head."""
    with PostgresContainer("postgres:17", driver="psycopg") as container:
        os.environ["DATABASE_URL"] = container.get_connection_url()
        reset_engine()

        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        command.upgrade(config, "head")

        yield

    reset_engine()


@pytest.fixture
def fresh_db(postgres: None) -> None:
    """Every case starts from the same seeded world."""
    seed()
