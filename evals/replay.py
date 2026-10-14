"""Replay a recorded run against a fresh database.

The model is never called. We take the tool calls the agent actually made,
re-execute only the writes, and then look at what the database holds. That
is the artifact being graded, not what the agent said it did.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ops_agent.db.models import Refund
from ops_agent.tools import writes
from ops_agent.tools.context import ToolContext
from ops_agent.tools.errors import ToolRefusal

WRITE_TOOLS = {"issue_refund", "escalate_to_human"}


def _args(raw: Any) -> dict[str, Any]:
    """pydantic-ai records tool arguments as a JSON string."""
    if isinstance(raw, str):
        loaded: dict[str, Any] = json.loads(raw or "{}")
        return loaded
    return dict(raw or {})


def replay(case: dict[str, Any], ctx: ToolContext, session: Session) -> None:
    """Re-run every write the agent attempted, in the order it attempted it.

    Reads are skipped because they cannot change state. Refusals are skipped
    because the original run saw the same refusal and nothing was written.
    """
    for call in case["tool_calls"]:
        if call["tool"] not in WRITE_TOOLS:
            continue
        args = _args(call["args"])
        try:
            if call["tool"] == "issue_refund":
                writes.issue_refund(ctx, writes.IssueRefundArgs(**args), session)
            else:
                writes.escalate_to_human(ctx, writes.EscalateArgs(**args))
        except (ToolRefusal, ValidationError):
            continue


def refunded_total(session: Session, order_id: str) -> int:
    total = session.scalar(
        select(func.coalesce(func.sum(Refund.amount_minor), 0)).where(
            Refund.order_id == order_id
        )
    )
    return total or 0
