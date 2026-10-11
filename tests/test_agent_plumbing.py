"""The loop works, the tools are registered, and the output validates.

No real model is called. TestModel invents a reply that satisfies the
output schema, which is enough to prove the wiring without spending
anything.

`call_tools` is restricted on purpose. TestModel makes up tool arguments
from the schema, and a made up refund amount would fail validation inside
the write tool. Those paths are already proved in test_tools.py with real
arguments, so here we only need the loop itself.
"""

from __future__ import annotations

from pydantic_ai.models.test import TestModel
from sqlalchemy.orm import Session

from ops_agent.agent.agent import MAX_MODEL_CALLS, USAGE_LIMITS, Deps, build_agent
from ops_agent.domain.contract import Decision, Outcome
from ops_agent.tools.context import ToolContext


def test_the_loop_produces_a_valid_outcome(
    db: Session, owner_readonly: ToolContext
) -> None:
    agent = build_agent("v1")
    deps = Deps(tool_ctx=owner_readonly, session=db)

    with agent.override(model=TestModel(call_tools=[])):
        result = agent.run_sync("I want a refund for ord_C1_01.", deps=deps)

    assert isinstance(result.output, Outcome)
    assert result.output.decision in set(Decision)


def test_a_tool_is_reachable_from_inside_the_loop(
    db: Session, owner_readonly: ToolContext
) -> None:
    """get_customer takes no arguments, so it is safe for a fake model."""
    agent = build_agent("v1")
    deps = Deps(tool_ctx=owner_readonly, session=db)

    with agent.override(model=TestModel(call_tools=["get_customer"])):
        result = agent.run_sync("Who am I?", deps=deps)

    called = [
        part.tool_name
        for message in result.all_messages()
        for part in getattr(message, "parts", [])
        if getattr(part, "tool_name", None)
    ]
    assert "get_customer" in called


def test_the_step_limit_is_wired() -> None:
    """A loop is not an answer. The cap exists and is carried to the runner."""
    assert USAGE_LIMITS.request_limit == MAX_MODEL_CALLS
    assert MAX_MODEL_CALLS <= 10
