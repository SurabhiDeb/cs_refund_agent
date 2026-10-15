"""Beat 9.4. Bad input and bad health, both answered honestly.

Nothing here reaches the model. A 422 is decided before the endpoint runs,
and /health never builds an agent.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ops_agent.api import app as app_module
from ops_agent.api.app import app

client = TestClient(app)

HEADERS = {"X-API-Key": "dev-key-owner"}


def test_empty_message_is_422() -> None:
    response = client.post("/chat", json={"message": ""}, headers=HEADERS)
    assert response.status_code == 422


def test_missing_message_is_422() -> None:
    response = client.post("/chat", json={}, headers=HEADERS)
    assert response.status_code == 422


def test_oversized_message_is_422() -> None:
    response = client.post("/chat", json={"message": "x" * 2001}, headers=HEADERS)
    assert response.status_code == 422


def test_bad_input_is_rejected_before_the_model() -> None:
    """422 comes from the request model, so nothing downstream runs. If this
    ever reached the agent it would cost money to find out."""
    response = client.post("/chat", json={"message": ""})
    assert response.status_code == 422


def test_health_is_ok_when_everything_is_up(db: Session) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_is_503_when_postgres_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "_postgres_ok", lambda: False)

    response = client.get("/health")
    assert response.status_code == 503

    body: dict[str, Any] = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["postgres"] is False


def test_health_is_503_when_redis_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "redis_ok", lambda: False)

    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["checks"]["redis"] is False
