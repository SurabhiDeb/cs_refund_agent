"""The write tools. One moves money, one hands over to a human.

Every guard that matters lives in this file, not in a prompt:
the kill switch, the cap, ownership, the remainder, and idempotency.
An attacker who fully controls the model still cannot get past them.
"""

from __future__ import annotations

import hashlib
import json
import uuid
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
    # Unique per attempt, not per content. An audit row records that
    # something happened, and the same thing can happen twice. Hashing the
    # content made the second occurrence collide and raise, losing the
    # record at exactly the moment it mattered.
    row_id = "aud_" + uuid.uuid4().hex[:24]

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


def reject_arguments(
    ctx: ToolContext,
    *,
    tool: str,
    arguments: dict[str, Any],
    detail: str,
) -> ToolRefusal:
    """Audit a write call whose arguments never passed validation.

    The argument model is built before the tool body is entered, so a
    malformed call used to raise before any audit row existed: an attacker
    probing the write path with bad arguments left no trace at all, and the
    exception ended the run instead of escalating. X9 gives that attempt a
    row and gives the model a refusal it can read.
    """
    # Stringified and clipped. These values came from the model, so they can
    # be any shape and any length, and neither json.dumps nor a String(32)
    # column should be the thing that loses the record.
    safe = {str(key)[:64]: str(value)[:500] for key, value in arguments.items()}
    attempted_order = safe.get("order_id")
    _audit(
        customer_id=ctx.customer_id,
        tool=tool,
        arguments=safe,
        allowed=False,
        reason="X9",
        order_id=attempted_order[:32] if attempted_order else None,
    )
    # The detail is deliberately vague. Echoing the validation message back
    # would describe the tool schema to whoever is probing it, which is R7.
    return ToolRefusal("X9", f"Those arguments were rejected: {detail}")


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

    # What this order has already paid out. Read inside the same locked
    # transaction, which is what makes both checks below safe. A CHECK
    # constraint cannot sum rows in another table.
    already = (
        session.scalar(
            select(func.coalesce(func.sum(Refund.amount_minor), 0)).where(
                Refund.order_id == order.id,
                Refund.status == RefundStatus.SUCCEEDED,
            )
        )
        or 0
    )

    # E4 first, ahead of the cap. An amount above the remainder is
    # impossible rather than borderline, so it gets the refusal that says so
    # instead of a human's attention.
    remainder = order.total_minor - already
    if args.amount_minor > remainder:
        raise refuse(
            "E4",
            f"Only {remainder} remains refundable on this order.",
        )

    # The cap, per order rather than per refund. A per refund cap stops one
    # large payment and nothing else: R5 blocks a second refund inside one
    # conversation and cannot see across conversations, so 3000 twice on the
    # same order moved 6000 under a 5000 cap. Summing subsumes the old
    # single amount check, since already is never negative.
    if already + args.amount_minor > settings.refund_cap_minor_units:
        raise refuse(
            "X1",
            f"{already + args.amount_minor} across this order is above the "
            f"cap of {settings.refund_cap_minor_units}. A human must "
            f"approve this.",
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
