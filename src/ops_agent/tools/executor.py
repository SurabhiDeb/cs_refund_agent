"""How a refund actually gets written.

The agent's tool does not choose. It asks whatever executor it was handed,
so the same agent code runs durably in the service and directly in tests
and evaluations. One write path per deployment, rather than two that drift
apart until a crash finds the difference.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from sqlalchemy.orm import Session

from ops_agent.tools import writes
from ops_agent.tools.context import ToolContext
from ops_agent.tools.errors import ToolRefusal


class RefundExecutor(Protocol):
    def __call__(
        self, ctx: ToolContext, args: writes.IssueRefundArgs, session: Session
    ) -> dict[str, Any]: ...


def direct_refund(
    ctx: ToolContext, args: writes.IssueRefundArgs, session: Session
) -> dict[str, Any]:
    """Write in this process. Tests and the eval harness use this, where a
    Temporal server would buy durability nobody is measuring."""
    return writes.issue_refund(ctx, args, session)


def workflow_refund(
    ctx: ToolContext,
    args: writes.IssueRefundArgs,
    session: Session,  # noqa: ARG001
) -> dict[str, Any]:
    """Hand the write to Temporal and wait for the answer.

    The session is accepted and ignored on purpose. The activity opens its
    own, because it may run in another process entirely, and keeping the
    signature identical is what lets the tool stay ignorant of its path.
    """
    from temporalio.client import Client

    from ops_agent.config import settings
    from ops_agent.workflows.refund import (
        TASK_QUEUE,
        RefundRequest,
        RefundWorkflow,
        derive_key,
    )

    # Both of these are enforced again here, not only inside issue_refund.
    # The activity builds a fresh ToolContext in another process, so the
    # kill switch and the one-write-per-conversation rule never reach it.
    # Checking at the edge of the workflow path is what closes that.
    if not ctx.write_enabled:
        raise ToolRefusal("KILL", "Refunds are currently disabled. Escalating instead.")
    if ctx.refunds_issued:
        raise ToolRefusal(
            "R5", "A refund has already been issued in this conversation."
        )

    request = RefundRequest(
        customer_id=ctx.customer_id,
        order_id=args.order_id,
        amount_minor=args.amount_minor,
        reason=args.reason,
    )

    async def execute() -> Any:
        client = await Client.connect(settings.temporal_address)
        return await client.execute_workflow(
            RefundWorkflow.run,
            request,
            # Derived, not random, so a retried HTTP call joins the running
            # workflow instead of starting a second payment.
            id=f"refund-{derive_key(request)}",
            task_queue=TASK_QUEUE,
        )

    result = asyncio.run(execute())

    if result.refused_code is not None:
        raise ToolRefusal(result.refused_code, "The refund was refused.")

    ctx.refunds_issued.append(str(result.refund_id))
    return {
        "refund_id": result.refund_id,
        "amount_minor": args.amount_minor,
        "status": result.status,
        "replayed": False,
    }
