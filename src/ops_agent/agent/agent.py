"""The agent loop, v1.

The model is pinned and reached through the AICredits gateway, which speaks
the OpenAI protocol. Nothing else in the project knows who the provider is.

Two cost guards live here. `request_limit` caps how many times the model may
be called in one run, and `max_tokens` caps each reply. Without them a looping
agent can spend real money on nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits
from sqlalchemy.orm import Session

from ops_agent.config import settings
from ops_agent.domain.contract import Outcome
from ops_agent.obs.metrics import TOOL_REFUSALS
from ops_agent.tools import reads, writes
from ops_agent.tools.context import ToolContext
from ops_agent.tools.errors import ToolRefusal

PROMPTS = Path(__file__).resolve().parent / "prompts"

# The model may be called at most this many times per run. Hitting the limit
# is itself an answer, handled as X7 by the caller.
MAX_MODEL_CALLS = 8


def load_prompt(version: str) -> str:
    """Prompts are immutable files. A change creates a new file, never an edit."""
    return (PROMPTS / f"{version}.md").read_text()


@dataclass
class Deps:
    """What the tools need, carried through the run by pydantic-ai."""

    tool_ctx: ToolContext
    session: Session


def _refused(error: ToolRefusal) -> dict[str, Any]:
    """A refusal is data the model should read, not a crash."""
    TOOL_REFUSALS.labels(code=error.code).inc()
    return {"refused": True, "code": error.code, "message": error.message}


def build_agent(prompt_version: str, *, may_write: bool = True) -> Agent[Deps, Outcome]:
    model = OpenAIChatModel(
        settings.llm_model,
        provider=OpenAIProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        ),
    )

    agent: Agent[Deps, Outcome] = Agent(
        model,
        deps_type=Deps,
        output_type=Outcome,
        instructions=load_prompt(prompt_version),
        model_settings=ModelSettings(temperature=0.0, max_tokens=600),
    )

    @agent.tool
    def get_order(ctx: RunContext[Deps], order_id: str) -> dict[str, Any]:
        """Facts about one order, including how much is still refundable."""
        try:
            return reads.get_order(
                ctx.deps.tool_ctx, reads.OrderArgs(order_id=order_id), ctx.deps.session
            )
        except ToolRefusal as error:
            return _refused(error)

    @agent.tool
    def get_order_items(ctx: RunContext[Deps], order_id: str) -> Any:
        """The line items on an order, with price and condition."""
        try:
            return reads.get_order_items(
                ctx.deps.tool_ctx, reads.OrderArgs(order_id=order_id), ctx.deps.session
            )
        except ToolRefusal as error:
            return _refused(error)

    @agent.tool
    def get_customer(ctx: RunContext[Deps]) -> dict[str, Any]:
        """The calling customer. Takes no argument, by design."""
        try:
            return reads.get_customer(ctx.deps.tool_ctx, ctx.deps.session)
        except ToolRefusal as error:
            return _refused(error)

    @agent.tool
    def get_refund_policy(ctx: RunContext[Deps], topic: str) -> Any:
        """Policy articles for a topic, which must be cited in the decision.
        Valid topics, exact match only. window, undelivered, partial, cap,
        non-refundable, damaged.
        """
        try:
            return reads.get_refund_policy(
                reads.PolicyArgs(topic=topic), ctx.deps.session
            )
        except ToolRefusal as error:
            return _refused(error)

    if may_write:

        @agent.tool
        def issue_refund(
            ctx: RunContext[Deps],
            order_id: str,
            amount_minor: int,
            reason: str,
            idempotency_key: str,
        ) -> dict[str, Any]:
            """Issue a refund. Amount is in minor units, so 2500 means 25.00."""
            raw = {
                "order_id": order_id,
                "amount_minor": amount_minor,
                "reason": reason,
                "idempotency_key": idempotency_key,
            }
            # Validation is part of the write path, so a failure is audited
            # and answered rather than raised. An uncaught ValidationError
            # here ends the run, which is the one thing rule 7 forbids.
            try:
                args = writes.IssueRefundArgs(**raw)
            except ValidationError as error:
                return _refused(
                    writes.reject_arguments(
                        ctx.deps.tool_ctx,
                        tool="issue_refund",
                        arguments=raw,
                        detail=f"{error.error_count()} invalid argument(s)",
                    )
                )
            try:
                return writes.issue_refund(ctx.deps.tool_ctx, args, ctx.deps.session)
            except ToolRefusal as error:
                return _refused(error)

    @agent.tool
    def escalate_to_human(
        ctx: RunContext[Deps], reason: str, summary: str
    ) -> dict[str, Any]:
        """Hand the case to a person. Always available."""
        # Clipped, never rejected. A summary over 2000 characters must not
        # be able to stop a handover: losing the tail of the text is always
        # better than losing the escalation. Rule 7.
        return writes.escalate_to_human(
            ctx.deps.tool_ctx,
            writes.EscalateArgs(
                reason=reason[:64] or "X6",
                summary=summary[:2000] or "no summary supplied",
            ),
        )

    return agent


USAGE_LIMITS = UsageLimits(request_limit=MAX_MODEL_CALLS)
