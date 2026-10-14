"""The tools are safe with no model in the loop.

If any test here fails, nothing downstream matters. These are the
zero-tolerance guarantees from CLAUDE.md, proved in plain Python.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ops_agent.config import settings
from ops_agent.db.models import AuditLog, Refund
from ops_agent.tools.context import ToolContext
from ops_agent.tools.errors import ToolRefusal
from ops_agent.tools.reads import OrderArgs, get_customer, get_order, get_order_items
from ops_agent.tools.writes import (
    EscalateArgs,
    IssueRefundArgs,
    escalate_to_human,
    issue_refund,
)


def refunded_total(session: Session, order_id: str) -> int:
    total = session.scalar(
        select(func.coalesce(func.sum(Refund.amount_minor), 0)).where(
            Refund.order_id == order_id
        )
    )
    return total or 0


# Reads


def test_owner_can_read_own_order(db: Session, owner: ToolContext) -> None:
    result = get_order(owner, OrderArgs(order_id="ord_C1_01"), db)
    assert result["total_minor"] == 3200
    assert result["refundable_remainder_minor"] == 3200


def test_unknown_order_is_refused(db: Session, owner: ToolContext) -> None:
    with pytest.raises(ToolRefusal) as caught:
        get_order(owner, OrderArgs(order_id="ord_99999"), db)
    assert caught.value.code == "R2"


def test_another_customers_order_is_refused(db: Session, owner: ToolContext) -> None:
    """C12 belongs to cus_002. cus_001 must not see it."""
    with pytest.raises(ToolRefusal) as caught:
        get_order(owner, OrderArgs(order_id="ord_C12_01"), db)
    assert caught.value.code == "R3"


def test_refusal_text_does_not_confirm_the_id(db: Session, owner: ToolContext) -> None:
    """R2 and R3 read identically, so probing ids reveals nothing."""
    with pytest.raises(ToolRefusal) as unknown:
        get_order(owner, OrderArgs(order_id="ord_99999"), db)
    with pytest.raises(ToolRefusal) as not_yours:
        get_order(owner, OrderArgs(order_id="ord_C12_01"), db)
    assert unknown.value.message.replace("ord_99999", "X") == (
        not_yours.value.message.replace("ord_C12_01", "X")
    )


def test_items_are_scoped_to_the_owner(db: Session, owner: ToolContext) -> None:
    with pytest.raises(ToolRefusal):
        get_order_items(owner, OrderArgs(order_id="ord_C12_01"), db)


def test_get_customer_takes_no_identity_argument(
    db: Session, owner: ToolContext
) -> None:
    result = get_customer(owner, db)
    assert result["customer_id"] == "cus_001"


# The kill switch


def test_kill_switch_blocks_every_refund(
    db: Session, owner_readonly: ToolContext
) -> None:
    with pytest.raises(ToolRefusal) as caught:
        issue_refund(
            owner_readonly,
            IssueRefundArgs(
                order_id="ord_C1_01",
                amount_minor=1000,
                reason="test",
                idempotency_key="kill-switch-test",
            ),
            db,
        )
    assert caught.value.code == "KILL"
    assert refunded_total(db, "ord_C1_01") == 0


def test_escalation_still_works_with_the_kill_switch_on(
    db: Session,  # noqa: ARG001  # needed so the audit insert has a database
    owner_readonly: ToolContext,
) -> None:
    result = escalate_to_human(
        owner_readonly,
        EscalateArgs(reason="X1", summary="over cap"),
    )
    assert result["status"] == "open"


# The cap


def test_refund_above_the_cap_is_refused(db: Session, owner: ToolContext) -> None:
    over = settings.refund_cap_minor_units + 1
    with pytest.raises(ToolRefusal) as caught:
        issue_refund(
            owner,
            IssueRefundArgs(
                order_id="ord_C9_01",
                amount_minor=over,
                reason="test",
                idempotency_key="over-the-cap",
            ),
            db,
        )
    assert caught.value.code == "X1"
    assert refunded_total(db, "ord_C9_01") == 0


def test_refund_exactly_at_the_cap_is_allowed(db: Session, owner: ToolContext) -> None:
    """The boundary. Off by one here is a real bug, not a rounding detail."""
    result = issue_refund(
        owner,
        IssueRefundArgs(
            order_id="ord_C9_01",
            amount_minor=settings.refund_cap_minor_units,
            reason="test",
            idempotency_key="exactly-the-cap",
        ),
        db,
    )
    assert result["amount_minor"] == settings.refund_cap_minor_units


# The remainder, rule E4


def test_fully_refunded_order_cannot_be_refunded_again(
    db: Session, owner: ToolContext
) -> None:
    """C5 is already refunded in full. Remainder is zero."""
    with pytest.raises(ToolRefusal) as caught:
        issue_refund(
            owner,
            IssueRefundArgs(
                order_id="ord_C5_01",
                amount_minor=100,
                reason="test",
                idempotency_key="no-remainder-left",
            ),
            db,
        )
    assert caught.value.code == "E4"
    assert refunded_total(db, "ord_C5_01") == 3000


def test_cannot_exceed_the_remainder(db: Session, owner: ToolContext) -> None:
    """C7 has 3500 total and 3000 already refunded, so 500 remains."""
    with pytest.raises(ToolRefusal) as caught:
        issue_refund(
            owner,
            IssueRefundArgs(
                order_id="ord_C7_01",
                amount_minor=3500,
                reason="customer asked for the full amount",
                idempotency_key="asked-for-too-much",
            ),
            db,
        )
    assert caught.value.code == "E4"
    assert refunded_total(db, "ord_C7_01") == 3000


def test_remainder_can_be_refunded_exactly(db: Session, owner: ToolContext) -> None:
    issue_refund(
        owner,
        IssueRefundArgs(
            order_id="ord_C7_01",
            amount_minor=500,
            reason="the remainder",
            idempotency_key="exactly-the-remainder",
        ),
        db,
    )
    assert refunded_total(db, "ord_C7_01") == 3500


def test_a_second_refund_in_one_conversation_is_refused(
    db: Session, owner: ToolContext
) -> None:
    """R5. One write per run, enforced in code, not in the prompt."""
    issue_refund(
        owner,
        IssueRefundArgs(
            order_id="ord_C1_01",
            amount_minor=2000,
            reason="first",
            idempotency_key="first-partial-refund",
        ),
        db,
    )
    with pytest.raises(ToolRefusal) as caught:
        issue_refund(
            owner,
            IssueRefundArgs(
                order_id="ord_C1_01",
                amount_minor=2000,
                reason="second",
                idempotency_key="second-partial-refund",
            ),
            db,
        )
    assert caught.value.code == "R5"


def test_two_partial_refunds_cannot_together_exceed_the_total(db: Session) -> None:
    """E4, across two conversations, where R5 cannot help.

    A fresh ToolContext each time, because that is what a second support
    conversation looks like. Separate keys, so idempotency does not save us.
    """
    first = ToolContext(customer_id="cus_001", write_enabled=True)
    second = ToolContext(customer_id="cus_001", write_enabled=True)

    issue_refund(
        first,
        IssueRefundArgs(
            order_id="ord_C1_01",
            amount_minor=2000,
            reason="first",
            idempotency_key="first-partial-refund",
        ),
        db,
    )
    with pytest.raises(ToolRefusal) as caught:
        issue_refund(
            second,
            IssueRefundArgs(
                order_id="ord_C1_01",
                amount_minor=2000,
                reason="second",
                idempotency_key="second-partial-refund",
            ),
            db,
        )
    assert caught.value.code == "E4"


# Idempotency


def test_the_same_key_twice_pays_once(db: Session, owner: ToolContext) -> None:
    args = IssueRefundArgs(
        order_id="ord_C1_01",
        amount_minor=3200,
        reason="test",
        idempotency_key="a-retried-request",
    )
    first = issue_refund(owner, args, db)
    second = issue_refund(owner, args, db)

    assert first["replayed"] is False
    assert second["replayed"] is True
    assert first["refund_id"] == second["refund_id"]
    assert refunded_total(db, "ord_C1_01") == 3200


# Audit


def test_a_refused_attempt_is_still_recorded(db: Session, owner: ToolContext) -> None:
    """The audit row survives the refusal, because it has its own transaction."""
    with pytest.raises(ToolRefusal):
        issue_refund(
            owner,
            IssueRefundArgs(
                order_id="ord_C9_01",
                amount_minor=99999,
                reason="test",
                idempotency_key="audited-refusal",
            ),
            db,
        )
    rows = db.scalars(
        select(AuditLog).where(
            AuditLog.tool == "issue_refund", AuditLog.allowed.is_(False)
        )
    ).all()
    assert any(row.reason == "X1" for row in rows)
