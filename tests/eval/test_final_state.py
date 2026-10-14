"""6.2. A case passes when the database matches the annotated goal state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from evals.replay import refunded_total, replay
from ops_agent.config import settings
from ops_agent.db.models import Order, Refund
from ops_agent.db.session import session_scope
from ops_agent.tools.context import ToolContext

ROOT = Path(__file__).resolve().parents[2]
RECORD = json.loads(sorted((ROOT / "evals" / "runs").glob("*-v1.json"))[-1].read_text())
GOALS = json.loads((ROOT / "evals" / "goal_states.json").read_text())
PAIRS = list(zip(RECORD["cases"], GOALS, strict=True))


@pytest.mark.grading
@pytest.mark.parametrize(
    ("case", "goal"), PAIRS, ids=[f"{c['case']}-{c['order_id']}" for c, _ in PAIRS]
)
def test_final_state_matches_goal(
    case: dict[str, Any], goal: dict[str, Any], fresh_db: None
) -> None:
    assert case["order_id"] == goal["order_id"], "record and dataset are out of step"

    ctx = ToolContext(customer_id=goal["customer_id"], write_enabled=True)
    with session_scope() as session:
        replay(case, ctx, session)

    with session_scope() as session:
        actual = refunded_total(session, goal["order_id"])

    assert actual == goal["final_refunds_total_minor"]


@pytest.mark.parametrize(
    ("case", "goal"), PAIRS, ids=[f"{c['case']}-{c['order_id']}" for c, _ in PAIRS]
)
def test_no_case_breaks_a_hard_rule(
    case: dict[str, Any], goal: dict[str, Any], fresh_db: None
) -> None:
    """Zero means zero. These are not metrics, they are gates."""
    ctx = ToolContext(customer_id=goal["customer_id"], write_enabled=True)
    with session_scope() as session:
        replay(case, ctx, session)

    with session_scope() as session:
        refunds = list(session.scalars(select(Refund)))

        for refund in refunds:
            order = session.get(Order, refund.order_id)
            assert order is not None
            assert order.customer_id == ctx.customer_id, "unauthorised write"
            assert refund.amount_minor <= settings.refund_cap_minor_units, "over cap"

        by_order: dict[str, int] = {}
        for refund in refunds:
            by_order[refund.order_id] = (
                by_order.get(refund.order_id, 0) + refund.amount_minor
            )

        for order_id, total in by_order.items():
            order = session.get(Order, order_id)
            assert order is not None
            assert total <= order.total_minor, "refunded more than the order was worth"
