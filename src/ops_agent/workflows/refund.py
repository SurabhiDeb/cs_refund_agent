"""Durable refunds.

A refund is one database write, and a process can die between deciding and
writing. Temporal makes the attempt survive that. The activity may run more
than once, so the idempotency key is derived from the request rather than
invented, and a replay is recognised as the same payment.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

# Workflow files run in a sandbox that reimports modules. Anything with real
# side effects, a database among them, has to be passed through untouched.
with workflow.unsafe.imports_passed_through():
    from opentelemetry import trace

    from ops_agent.config import settings
    from ops_agent.db.models import Refund, RefundStatus
    from ops_agent.db.session import session_scope
    from ops_agent.tools import writes
    from ops_agent.tools.context import ToolContext
    from ops_agent.tools.errors import ToolRefusal

TASK_QUEUE = "ops-agent-refunds"


@dataclass(frozen=True)
class RefundRequest:
    customer_id: str
    order_id: str
    amount_minor: int
    reason: str


@dataclass(frozen=True)
class RefundResult:
    refund_id: str | None
    status: str
    refused_code: str | None = None


def derive_key(request: RefundRequest) -> str:
    """The same request always produces the same key.

    A random key makes a retry look like a new payment, which is how a crash
    becomes a double refund. This function is why the retry is safe.
    """
    raw = (
        f"{request.customer_id}:{request.order_id}:"
        f"{request.amount_minor}:{request.reason}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


@activity.defn
def issue_refund_activity(request: RefundRequest) -> RefundResult:
    """The only place money moves. Written to be safe on a second run."""
    ctx = ToolContext(customer_id=request.customer_id, write_enabled=True)
    # The interceptor already opened a span for this activity. Attributes go
    # on it, so the refund is reconstructable from the trace rather than
    # from the log line next to it.
    span = trace.get_current_span()
    span.set_attribute("ops.order_id", request.order_id)
    span.set_attribute("ops.amount_minor", request.amount_minor)
    span.set_attribute("ops.idempotency_key", derive_key(request))
    args = writes.IssueRefundArgs(
        order_id=request.order_id,
        amount_minor=request.amount_minor,
        reason=request.reason,
        idempotency_key=derive_key(request),
    )
    try:
        with session_scope() as session:
            result = writes.issue_refund(ctx, args, session)
    except ToolRefusal as error:
        # A refusal is a final answer, not a transient failure. Returning it
        # instead of raising stops Temporal retrying something that will be
        # refused every time.

        return RefundResult(refund_id=None, status="refused", refused_code=error.code)

    # Deliberate pause, off by default. It holds the activity open after the
    # money has been committed but before Temporal hears about it, which is
    # the only window where a crash could cause a second payment.
    if settings.refund_activity_delay_seconds:
        time.sleep(settings.refund_activity_delay_seconds)
    span.set_attribute("ops.refund_id", str(result["refund_id"]))
    span.set_attribute("ops.replayed", bool(result.get("replayed", False)))
    return RefundResult(
        refund_id=str(result["refund_id"]), status=str(result["status"])
    )


@activity.defn
def confirm_with_processor(refund_id: str) -> str:
    """Stand in for the payment processor.

    There is no real processor in this project. What matters is that a step
    after the database write can fail, because that is the case compensation
    exists for.
    """
    if settings.processor_rejects:
        raise ApplicationError("processor rejected the refund", non_retryable=True)
    return refund_id


@activity.defn
def mark_refund_failed(refund_id: str) -> None:
    """Compensation. The money never left, so the row must not claim it did."""
    with session_scope() as session:
        refund = session.get(Refund, refund_id)
        if refund is not None:
            refund.status = RefundStatus.FAILED


@workflow.defn
class RefundWorkflow:
    @workflow.run
    async def run(self, request: RefundRequest) -> RefundResult:
        result = await workflow.execute_activity(
            issue_refund_activity,
            request,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_attempts=5,
            ),
        )
        if result.refund_id is None:
            return result

        try:
            await workflow.execute_activity(
                confirm_with_processor,
                result.refund_id,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        except ActivityError:
            # The money did not leave. Undo the claim that it did, then say
            # so. Compensation is its own activity, so it retries on its own
            # and survives a crash the same way the refund does.
            await workflow.execute_activity(
                mark_refund_failed,
                result.refund_id,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            return RefundResult(
                refund_id=result.refund_id, status="failed", refused_code="X8"
            )

        return result
