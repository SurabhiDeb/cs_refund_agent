"""Run one case and record everything about it.

A run record is the primary artifact of this project. If it is not in the
record, it did not happen, and you cannot do error analysis on a summary.

Provenance is recorded so a number can always be traced back to the exact
prompt, dataset, code, and model that produced it.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ops_agent.agent.agent import USAGE_LIMITS, Deps, build_agent, load_prompt
from ops_agent.config import settings
from ops_agent.db.models import Refund
from ops_agent.domain.contract import Decision, Outcome
from ops_agent.tools.context import ToolContext

ROOT = Path(__file__).resolve().parents[3]
GOALS = ROOT / "evals" / "goal_states.json"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()


def _git_dirty() -> bool:
    """Tracked changes only.

    chatbot-lab recorded every run as dirty because untracked output files
    counted. `--untracked-files=no` is the fix.
    """
    out = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return bool(out.strip())


def _refunded(session: Session, order_id: str) -> int:
    total = session.scalar(
        select(func.coalesce(func.sum(Refund.amount_minor), 0)).where(
            Refund.order_id == order_id
        )
    )
    return total or 0


def _cost_inr(input_tokens: int, output_tokens: int) -> float:
    return round(
        input_tokens * settings.llm_input_inr_per_million / 1_000_000
        + output_tokens * settings.llm_output_inr_per_million / 1_000_000,
        4,
    )


def _tool_calls(messages: list[Any]) -> list[dict[str, Any]]:
    """Every tool the model asked for, in order, with its arguments."""
    calls: list[dict[str, Any]] = []
    for message in messages:
        for part in getattr(message, "parts", []):
            name = getattr(part, "tool_name", None)
            if name and hasattr(part, "args"):
                calls.append({"tool": name, "args": part.args})
    return calls


@dataclass(frozen=True)
class Provenance:
    """Computed once per run, identical for every case in it."""

    prompt_version: str
    prompt_sha: str
    dataset_sha: str
    git_sha: str
    git_dirty: bool
    model: str

    @staticmethod
    def build(prompt_version: str) -> Provenance:
        return Provenance(
            prompt_version=prompt_version,
            prompt_sha=_sha(load_prompt(prompt_version)),
            dataset_sha=_sha(GOALS.read_text()),
            git_sha=_git_sha(),
            git_dirty=_git_dirty(),
            model=settings.llm_model,
        )


def run_case(
    goal: dict[str, Any],
    *,
    prompt_version: str,
    session: Session,
    write_enabled: bool,
) -> dict[str, Any]:
    """One case, start to finish, with the whole trajectory recorded."""
    agent = build_agent(prompt_version)
    tool_ctx = ToolContext(customer_id=goal["customer_id"], write_enabled=write_enabled)
    deps = Deps(tool_ctx=tool_ctx, session=session)
    order_id = goal["order_id"]

    refunded_before = _refunded(session, order_id)
    started = time.monotonic()

    outcome: Outcome | None = None
    failure: str | None = None
    messages_json = "[]"
    input_tokens = 0
    output_tokens = 0

    try:
        result = agent.run_sync(goal["request"], deps=deps, usage_limits=USAGE_LIMITS)
        outcome = result.output
        messages_json = result.all_messages_json().decode()
        usage = result.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        calls = _tool_calls(result.all_messages())
    except UsageLimitExceeded:
        # X7. A loop is not an answer, so the run escalates.
        failure = "X7"
        calls = []
    except UnexpectedModelBehavior as error:
        # X6. The model's own output could not be understood. Fail safe.
        failure = f"X6: {error}"
        calls = []

    elapsed = round(time.monotonic() - started, 3)
    refunded_after = _refunded(session, order_id)

    # When the run blew up, the decision is escalate, never silence.
    decision = outcome.decision if outcome else Decision.ESCALATE
    reason_code = outcome.reason_code if outcome else (failure or "X8")

    return {
        "case": goal["case"],
        "order_id": order_id,
        "request": goal["request"],
        "expected_decision": goal["expected_decision"],
        "expected_reason": goal["expected_reason"],
        "expected_refund_minor": goal["expected_refund_minor"],
        "expected_final_refunds_total_minor": goal["final_refunds_total_minor"],
        "decision": str(decision),
        "reason_code": reason_code,
        "outcome": outcome.model_dump(mode="json") if outcome else None,
        "failure": failure,
        "tool_calls": calls,
        "step_count": len(calls),
        "messages": json.loads(messages_json),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_inr": _cost_inr(input_tokens, output_tokens),
        "seconds": elapsed,
        # The assertion that actually matters, from the database itself.
        "refunds_before_minor": refunded_before,
        "refunds_after_minor": refunded_after,
        "refund_written_minor": refunded_after - refunded_before,
    }
