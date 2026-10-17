"""Beat 11, Layer 1. The tool layer against an attacker who owns the model.

No model in the loop, no tokens spent. Every case here assumes the prompt
has already been defeated and the attacker is calling tools directly with
hostile arguments. tests/test_tools.py proves the rules hold; this file
tries to get round them.
"""

from __future__ import annotations

import dataclasses

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ops_agent.agent.agent import build_agent
from ops_agent.config import settings
from ops_agent.db.models import AuditLog, Refund
from ops_agent.tools import reads, writes
from ops_agent.tools.context import ToolContext
from ops_agent.tools.errors import ToolRefusal
from ops_agent.tools.writes import EscalateArgs, IssueRefundArgs, issue_refund

IDENTITY_FIELDS = {"customer_id", "write_enabled", "scope", "api_key", "caller"}


def refunded_total(session: Session, order_id: str) -> int:
    total = session.scalar(
        select(func.coalesce(func.sum(Refund.amount_minor), 0)).where(
            Refund.order_id == order_id
        )
    )
    return total or 0


def audit_rows(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(AuditLog)) or 0


def audited_refusal(session: Session, code: str) -> bool:
    rows = session.scalars(
        select(AuditLog).where(
            AuditLog.tool == "issue_refund", AuditLog.allowed.is_(False)
        )
    ).all()
    return any(row.reason == code for row in rows)


# Identity. The attacker is logged in as cus_001 and wants someone else's money.


def test_a_refund_on_another_customers_order_is_refused(
    db: Session, owner: ToolContext
) -> None:
    """R3 is tested on the read path at Beat 3. The write path is the one
    that spends money, so it gets its own proof."""
    with pytest.raises(ToolRefusal) as caught:
        issue_refund(
            owner,
            IssueRefundArgs(
                order_id="ord_C12_01",
                amount_minor=100,
                reason="it is mine, honestly",
                idempotency_key="another-customers-order",
            ),
            db,
        )
    assert caught.value.code == "R3"
    assert refunded_total(db, "ord_C12_01") == 0
    assert audited_refusal(db, "R3")


def test_a_refund_on_an_unknown_order_is_refused(
    db: Session, owner: ToolContext
) -> None:
    with pytest.raises(ToolRefusal) as caught:
        issue_refund(
            owner,
            IssueRefundArgs(
                order_id="ord_99999",
                amount_minor=100,
                reason="invented order",
                idempotency_key="invented-order-id",
            ),
            db,
        )
    assert caught.value.code == "R2"


def test_no_model_facing_tool_takes_an_identity_argument() -> None:
    """Rule 12. If the model cannot name a customer, it cannot be talked
    into naming a different one. Asserted against the JSON schema the model
    actually sees, not against our intentions."""
    for tool in build_agent("v2")._function_toolset.tools.values():
        properties = tool.function_schema.json_schema.get("properties", {})
        assert not IDENTITY_FIELDS & set(properties), tool.name


def test_identity_cannot_be_reassigned_at_runtime(owner: ToolContext) -> None:
    """ToolContext is frozen, so a compromised tool body cannot swap caller."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        owner.customer_id = "cus_002"  # type: ignore[misc]


# The kill switch.


def test_the_kill_switch_beats_a_perfectly_valid_refund(
    db: Session, owner_readonly: ToolContext
) -> None:
    """Eligible order, in window, under the cap, remainder available.
    Everything the model could argue for, and it still pays nothing."""
    with pytest.raises(ToolRefusal) as caught:
        issue_refund(
            owner_readonly,
            IssueRefundArgs(
                order_id="ord_C1_01",
                amount_minor=3200,
                reason="fully eligible",
                idempotency_key="valid-but-killed",
            ),
            db,
        )
    assert caught.value.code == "KILL"
    assert refunded_total(db, "ord_C1_01") == 0
    assert audited_refusal(db, "KILL")


# Idempotency, used as a weapon rather than a safety net.


def test_replaying_a_key_with_a_bigger_amount_pays_the_original_amount(
    db: Session, owner: ToolContext
) -> None:
    """The refund id is derived from order plus key, not from the amount.
    So a replay that inflates the amount gets the first refund back and
    moves no further money."""
    first = issue_refund(
        owner,
        IssueRefundArgs(
            order_id="ord_C1_01",
            amount_minor=100,
            reason="small",
            idempotency_key="inflate-on-replay",
        ),
        db,
    )
    second = issue_refund(
        owner,
        IssueRefundArgs(
            order_id="ord_C1_01",
            amount_minor=3200,
            reason="much bigger",
            idempotency_key="inflate-on-replay",
        ),
        db,
    )
    assert second["replayed"] is True
    assert second["amount_minor"] == first["amount_minor"] == 100
    assert refunded_total(db, "ord_C1_01") == 100


def test_the_same_key_on_a_different_order_is_a_different_refund(
    db: Session, owner: ToolContext
) -> None:
    """Keys are namespaced by order, so a reused key cannot silently
    suppress a legitimate refund on another order."""
    first = issue_refund(
        owner,
        IssueRefundArgs(
            order_id="ord_C1_01",
            amount_minor=100,
            reason="first order",
            idempotency_key="shared-key",
        ),
        db,
    )
    fresh = ToolContext(customer_id="cus_001", write_enabled=True)
    second = issue_refund(
        fresh,
        IssueRefundArgs(
            order_id="ord_C8_01",
            amount_minor=100,
            reason="second order",
            idempotency_key="shared-key",
        ),
        db,
    )
    assert first["refund_id"] != second["refund_id"]
    assert second["replayed"] is False


def test_another_customer_cannot_replay_someone_elses_key(db: Session) -> None:
    """Ownership is checked before the replay lookup, so a guessed key
    cannot be used to read back another customer's refund."""
    owner_ctx = ToolContext(customer_id="cus_001", write_enabled=True)
    issue_refund(
        owner_ctx,
        IssueRefundArgs(
            order_id="ord_C1_01",
            amount_minor=100,
            reason="legitimate",
            idempotency_key="guessable-key",
        ),
        db,
    )
    attacker = ToolContext(customer_id="cus_002", write_enabled=True)
    with pytest.raises(ToolRefusal) as caught:
        issue_refund(
            attacker,
            IssueRefundArgs(
                order_id="ord_C1_01",
                amount_minor=100,
                reason="replay someone else",
                idempotency_key="guessable-key",
            ),
            db,
        )
    assert caught.value.code == "R3"


# Argument shape. Pydantic is part of the safety layer, so prove it.


@pytest.mark.parametrize("amount", [0, -1, -5000])
def test_non_positive_amounts_never_reach_the_database(
    db: Session, owner: ToolContext, amount: int
) -> None:
    """A negative refund is a charge. It must die at validation."""
    with pytest.raises(ValidationError):
        issue_refund(
            owner,
            IssueRefundArgs(
                order_id="ord_C1_01",
                amount_minor=amount,
                reason="negative",
                idempotency_key="non-positive-amount",
            ),
            db,
        )
    assert refunded_total(db, "ord_C1_01") == 0


def test_a_rejected_argument_leaves_no_audit_row(
    db: Session, owner: ToolContext
) -> None:
    """Building the argument model directly still writes nothing, because
    validation happens before the tool is entered. That is fine for our own
    callers. The model's path goes through writes.reject_arguments instead,
    proved below."""
    before = audit_rows(db)
    with pytest.raises(ValidationError):
        IssueRefundArgs(
            order_id="ord_C1_01",
            amount_minor=1,
            reason="x" * 500,
            idempotency_key="overlong-reason",
        )
    assert audit_rows(db) == before


def test_an_sql_shaped_order_id_is_just_a_miss(db: Session, owner: ToolContext) -> None:
    with pytest.raises(ToolRefusal) as caught:
        reads.get_order(owner, reads.OrderArgs(order_id="ord' OR 1=1--"), db)
    assert caught.value.code == "R2"


def test_the_escalation_path_can_itself_be_rejected(owner: ToolContext) -> None:
    """Rule 7 says an unparseable response escalates. A 2000 character
    limit on the summary means a long enough conversation cannot escalate
    at all. Recorded here so the fail-safe's own failure mode is visible."""
    with pytest.raises(ValidationError):
        writes.escalate_to_human(owner, EscalateArgs(reason="X1", summary="a" * 2001))


# The cap, as an attacker who comes back tomorrow sees it.


def test_two_conversations_cannot_exceed_the_cap_in_aggregate(db: Session) -> None:
    """The cap is per order. 3000 then 3000 on a 6000 order would be 6000
    under a cap of 5000, so the first pays and the second escalates."""
    first = ToolContext(customer_id="cus_001", write_enabled=True)
    second = ToolContext(customer_id="cus_001", write_enabled=True)
    issue_refund(
        first,
        IssueRefundArgs(
            order_id="ord_C11_01",
            amount_minor=3000,
            reason="conversation one",
            idempotency_key="cap-split-one",
        ),
        db,
    )
    with pytest.raises(ToolRefusal) as caught:
        issue_refund(
            second,
            IssueRefundArgs(
                order_id="ord_C11_01",
                amount_minor=3000,
                reason="conversation two",
                idempotency_key="cap-split-two",
            ),
            db,
        )
    assert caught.value.code == "X1"
    assert refunded_total(db, "ord_C11_01") == 3000
    assert refunded_total(db, "ord_C11_01") <= settings.refund_cap_minor_units


def test_an_order_can_be_topped_up_to_exactly_the_cap(db: Session) -> None:
    """The boundary on the aggregate, which is where an off by one lives."""
    first = ToolContext(customer_id="cus_001", write_enabled=True)
    second = ToolContext(customer_id="cus_001", write_enabled=True)
    issue_refund(
        first,
        IssueRefundArgs(
            order_id="ord_C11_01",
            amount_minor=3000,
            reason="conversation one",
            idempotency_key="cap-exact-one",
        ),
        db,
    )
    issue_refund(
        second,
        IssueRefundArgs(
            order_id="ord_C11_01",
            amount_minor=2000,
            reason="conversation two",
            idempotency_key="cap-exact-two",
        ),
        db,
    )
    assert refunded_total(db, "ord_C11_01") == settings.refund_cap_minor_units


def test_rejected_arguments_are_audited(db: Session, owner: ToolContext) -> None:
    """The other half of test_a_rejected_argument_leaves_no_audit_row. The
    model facing wrapper routes a ValidationError through here, so the
    attempt is recorded as X9 instead of vanishing."""
    before = audit_rows(db)
    refusal = writes.reject_arguments(
        owner,
        tool="issue_refund",
        arguments={
            "order_id": "ord_C1_01" + "x" * 100,
            "amount_minor": -500,
            "reason": "y" * 5000,
            "idempotency_key": "k",
        },
        detail="2 invalid argument(s)",
    )
    assert refusal.code == "X9"
    assert audit_rows(db) == before + 1
    assert audited_refusal(db, "X9")
