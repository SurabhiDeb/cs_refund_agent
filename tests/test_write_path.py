"""There is one write path, and a setting chooses it.

Beat 8 made refunds durable and only the workflow path got that. /chat
wrote directly, so everything durability bought applied to a path the
service never took. This proves the service can take it.
"""

from __future__ import annotations

import pytest

from ops_agent.api.app import refund_executor
from ops_agent.tools.executor import direct_refund, workflow_refund


def test_default_is_the_direct_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests and evals write in process, where Temporal buys nothing."""
    monkeypatch.setattr("ops_agent.api.app.settings.durable_refunds", False)
    assert refund_executor() is direct_refund


def test_durable_refunds_routes_through_temporal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ops_agent.api.app.settings.durable_refunds", True)
    assert refund_executor() is workflow_refund


def test_the_workflow_path_still_honours_the_kill_switch() -> None:
    """The activity builds its own ToolContext in another process, so the
    kill switch cannot reach it. It is re-checked before the workflow
    starts, and this is the test that says so."""
    from ops_agent.tools.context import ToolContext
    from ops_agent.tools.errors import ToolRefusal
    from ops_agent.tools.writes import IssueRefundArgs

    ctx = ToolContext(customer_id="cus_001", write_enabled=False)
    args = IssueRefundArgs(
        order_id="ord_C1_01",
        amount_minor=100,
        reason="test",
        idempotency_key="kill-switch-on-workflow-path",
    )
    with pytest.raises(ToolRefusal) as caught:
        workflow_refund(ctx, args, None)  # type: ignore[arg-type]
    assert caught.value.code == "KILL"
