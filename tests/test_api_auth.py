"""Beat 9.7. The gate at the front door, tested.

Curl proves a thing once. These run on every push. The point of each test is
not that the status code is 401, but that nothing behind the door moved.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ops_agent.agent.agent import build_agent
from ops_agent.api.app import app

client = TestClient(app)

ASK = {"message": "refund me 3200 on ord_C1_01"}


def _audit_rows(session: Session) -> int:
    from ops_agent.db.models import AuditLog

    return session.scalar(select(func.count()).select_from(AuditLog)) or 0


def test_missing_key_is_rejected(db: Session) -> None:
    assert client.post("/chat", json=ASK).status_code == 401


def test_unknown_key_is_rejected(db: Session) -> None:
    response = client.post("/chat", json=ASK, headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


def test_no_tool_runs_without_a_key(db: Session) -> None:
    """The real assertion of Beat 9.

    A 401 is only the symptom. What matters is that no tool was reached, and
    the audit log is where a tool attempt would have left its mark.
    """
    before = _audit_rows(db)
    client.post("/chat", json=ASK)
    client.post("/chat", json=ASK, headers={"X-API-Key": "wrong-key"})
    db.expire_all()
    assert _audit_rows(db) == before


def test_read_scope_gets_no_refund_tool() -> None:
    """A read-only caller cannot be talked into a refund, because there is
    nothing to talk to. The tool is never registered."""
    assert "issue_refund" in build_agent("v2", may_write=True)._function_toolset.tools
    assert (
        "issue_refund" not in build_agent("v2", may_write=False)._function_toolset.tools
    )


def test_escalation_survives_read_scope() -> None:
    """Refusing to refund must never mean refusing to help."""
    tools = build_agent("v2", may_write=False)._function_toolset.tools
    assert "escalate_to_human" in tools


def test_unknown_run_id_is_404(db: Session) -> None:
    assert client.get("/runs/run_doesnotexist").status_code == 404
