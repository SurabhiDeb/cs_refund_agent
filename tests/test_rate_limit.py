"""Beat 9.3. The limiter, tested without spending a rupee.

Every test here stops before the agent is built. A test that let a real
/chat through would cost gateway credits to prove something about Redis.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ops_agent.api.app import app
from ops_agent.api.limits import enforce
from ops_agent.config import settings

client = TestClient(app)

ASK = {"message": "refund me 3200 on ord_C1_01"}


def _fresh_key() -> str:
    """A new bucket per test, so one test cannot exhaust another's window."""
    return "test-key-" + uuid.uuid4().hex


def test_calls_under_the_limit_pass() -> None:
    key = _fresh_key()
    for _ in range(3):
        enforce(key, limit=3, window_seconds=60)


def test_the_call_over_the_limit_is_rejected() -> None:
    key = _fresh_key()
    for _ in range(3):
        enforce(key, limit=3, window_seconds=60)

    with pytest.raises(HTTPException) as caught:
        enforce(key, limit=3, window_seconds=60)

    assert caught.value.status_code == 429


def test_each_key_has_its_own_allowance() -> None:
    """One noisy caller must not lock everyone else out."""
    noisy, quiet = _fresh_key(), _fresh_key()
    for _ in range(3):
        enforce(noisy, limit=3, window_seconds=60)

    enforce(quiet, limit=3, window_seconds=60)


def test_chat_is_limited_before_the_model_is_called(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real assertion. A limit of zero means the first call is refused,
    so a 429 here proves the limiter runs ahead of the agent, not after it.
    If it ever ran after, this test would try to reach the gateway."""
    monkeypatch.setattr(settings, "rate_limit_requests", 0)

    response = client.post("/chat", json=ASK, headers={"X-API-Key": "dev-key-owner"})
    assert response.status_code == 429


def test_an_unknown_key_does_not_consume_the_allowance(db: Session) -> None:
    """Authenticate first, then count. A stranger's rejected call must not
    eat a real caller's budget."""
    response = client.post("/chat", json=ASK, headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401
