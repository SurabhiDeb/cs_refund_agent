"""The write tools. One moves money, one hands over to a human.

Every guard that matters lives in this file, not in a prompt:
the kill switch, the cap, ownership, the remainder, and idempotency.
An attacker who fully controls the model still cannot get past them.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ops_agent.config import settings
from ops_agent.db.models import AuditLog, Order, Refund, RefundStatus
from ops_agent.db.session import session_scope
from ops_agent.tools.context import ToolContext
from ops_agent.tools.errors import ToolRefusal


class IssueRefundArgs(BaseModel):
    order_id: str = Field(min_length=1, max_length=32)
    # Minor units, integer, at least 1. No floats near money.
    amount_minor: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=200)
    # Supplied by the caller so a retry is recognisable as the same request.
    idempotency_key: str = Field(min_length=8, max_length=64)


class EscalateArgs(BaseModel):
    reason: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=2000)


def _audit(
    *,
    customer_id: str | None,
    tool: str,
    arguments: dict[str, Any],
    allowed: bool,
    reason: str | None = None,
    order_id: str | None = None,
) -> None:
    """Record the attempt in its own transaction.

    Deliberately a separate session. If it shared the caller's transaction,
    a refusal would roll the audit row back and the refused attempt would
    leave no trace, which is exactly the record you most want to keep.
    """
    payload = json.dumps(arguments, sort_keys=True)
    row_id = (
        "aud_"
        + hashlib.sha256(f"{tool}{payload}{allowed}{reason}".encode()).hexdigest()[:24]
    )
    with session_scope() as audit_session:
        audit_session.add(
            AuditLog(
                id=row_id,
                customer_id=customer_id,
                tool=tool,
                arguments=payload,
                allowed=allowed,
                reason=reason,
                order_id=order_id,
            )
        )


def _refund_id(order_id: str, idempotency_key: str) -> str:
    """Derived, not random. The same request always maps to the same id."""
    digest = hashlib.sha256(f"{order_id}:{idempotency_key}".encode()).hexdigest()
    return "ref_" + digest[:24]


def issue_refund(
    ctx: ToolContext, args: IssueRefundArgs, session: Session
) -> dict[str, Any]:
    """Issue a refund, or refuse. The only tool that spends money."""
    arguments = args.model_dump()

    def refuse(code: str, message: str) -> ToolRefusal:
        _audit(
            customer_id=ctx.customer_id,
            tool="issue_refund",
            arguments=arguments,
            allowed=False,
            reason=code,
            order_id=args.order_id,
        )
        return ToolRefusal(code, message)

    # The kill switch. Checked before anything else.
    if not ctx.write_enabled:
        raise refuse("KILL", "Refunds are currently disabled. Escalating instead.")

    # Lock the order row for the rest of this transaction. Without the lock,
    # two concurrent refunds could each read the same remainder and both pass.
    order = session.get(Order, args.order_id, with_for_update=True)
    if order is None:
        raise refuse("R2", f"No order with id {args.order_id}.")
    if order.customer_id != ctx.customer_id:
        raise refuse("R3", f"No order with id {args.order_id}.")

    # Idempotency. A replay returns the original refund and writes nothing.
    existing = session.get(Refund, _refund_id(args.order_id, args.idempotency_key))
    if existing is not None:
        _audit(
            customer_id=ctx.customer_id,
            tool="issue_refund",
            arguments=arguments,
            allowed=True,
            reason="replay, no new refund",
            order_id=args.order_id,
        )
        return {
            "refund_id": existing.id,
            "amount_minor": existing.amount_minor,
            "status": str(existing.status),
            "replayed": True,
        }

    # R5. One refund per conversation, enforced here rather than in the
    # prompt. A second key for the same ask is a new payment, not a retry.
    if ctx.refunds_issued:
        raise refuse("R5", "A refund has already been issued in this conversation.")

    # The cap. In code, so it holds even if the prompt is ignored or attacked.
    if args.amount_minor > settings.refund_cap_minor_units:
        raise refuse(
            "X1",
            f"{args.amount_minor} is above the cap of "
            f"{settings.refund_cap_minor_units}. A human must approve this.",
        )

    # E4. Read inside the same locked transaction, which is what makes this
    # safe. A CHECK constraint cannot sum rows in another table.
    already = (
        session.scalar(
            select(func.coalesce(func.sum(Refund.amount_minor), 0)).where(
                Refund.order_id == order.id
            )
        )
        or 0
    )
    remainder = order.total_minor - already
    if args.amount_minor > remainder:
        raise refuse(
            "E4",
            f"Only {remainder} remains refundable on this order.",
        )

    refund = Refund(
        id=_refund_id(args.order_id, args.idempotency_key),
        order_id=order.id,
        amount_minor=args.amount_minor,
        reason=args.reason,
        idempotency_key=args.idempotency_key,
        status=RefundStatus.SUCCEEDED,
    )
    session.add(refund)
    session.flush()
    ctx.refunds_issued.append(refund.id)

    _audit(
        customer_id=ctx.customer_id,
        tool="issue_refund",
        arguments=arguments,
        allowed=True,
        reason=None,
        order_id=order.id,
    )
    return {
        "refund_id": refund.id,
        "amount_minor": refund.amount_minor,
        "status": str(refund.status),
        "replayed": False,
    }


def escalate_to_human(ctx: ToolContext, args: EscalateArgs) -> dict[str, Any]:
    """Hand the case to a person. Always available, kill switch or not."""
    ticket_id = (
        "tkt_"
        + hashlib.sha256(
            f"{ctx.customer_id}:{args.reason}:{args.summary}".encode()
        ).hexdigest()[:20]
    )
    _audit(
        customer_id=ctx.customer_id,
        tool="escalate_to_human",
        arguments=args.model_dump(),
        allowed=True,
        reason=args.reason,
    )
    return {"ticket_id": ticket_id, "status": "open"}
