"""The read tools. Four of them, none of which can change anything.

Every tool that touches an order checks ownership first. The check lives
here, in the tool, not in the prompt and not in the caller.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ops_agent.db.models import Customer, Order, OrderItem, Policy, Refund
from ops_agent.tools.context import ToolContext
from ops_agent.tools.errors import ToolRefusal


class OrderArgs(BaseModel):
    order_id: str = Field(min_length=1, max_length=32)


class PolicyArgs(BaseModel):
    topic: str = Field(min_length=1, max_length=64)


def _owned_order(ctx: ToolContext, order_id: str, session: Session) -> Order:
    """Fetch an order, or refuse. Never returns someone else's order."""
    order = session.get(Order, order_id)
    if order is None:
        raise ToolRefusal("R2", f"No order with id {order_id}.")
    if order.customer_id != ctx.customer_id:
        # Same refusal text as R2 on purpose. Saying "that exists but is not
        # yours" would confirm the id to someone guessing.
        raise ToolRefusal("R3", f"No order with id {order_id}.")
    return order


def get_order(ctx: ToolContext, args: OrderArgs, session: Session) -> dict[str, Any]:
    order = _owned_order(ctx, args.order_id, session)
    refunded = session.scalar(
        select(func.coalesce(func.sum(Refund.amount_minor), 0)).where(
            Refund.order_id == order.id
        )
    )
    return {
        "order_id": order.id,
        "status": str(order.status),
        "placed_at": order.placed_at.isoformat(),
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "total_minor": order.total_minor,
        "currency": order.currency,
        "payment_method": order.payment_method,
        "already_refunded_minor": refunded or 0,
        "refundable_remainder_minor": order.total_minor - (refunded or 0),
    }


def get_order_items(
    ctx: ToolContext, args: OrderArgs, session: Session
) -> list[dict[str, Any]]:
    order = _owned_order(ctx, args.order_id, session)
    items = session.scalars(
        select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)
    ).all()
    return [
        {
            "item_id": item.id,
            "sku": item.sku,
            "name": item.name,
            "quantity": item.quantity,
            "unit_price_minor": item.unit_price_minor,
            "condition": str(item.condition),
            "refundable": item.refundable,
        }
        for item in items
    ]


def get_customer(ctx: ToolContext, session: Session) -> dict[str, Any]:
    """Takes no arguments. The identity is the context, never a parameter."""
    customer = session.get(Customer, ctx.customer_id)
    if customer is None:
        raise ToolRefusal("X5", "Caller identity could not be resolved.")
    prior = session.scalar(
        select(func.count())
        .select_from(Refund)
        .join(Order, Order.id == Refund.order_id)
        .where(Order.customer_id == ctx.customer_id)
    )
    return {
        "customer_id": customer.id,
        "created_at": customer.created_at.isoformat(),
        "prior_refund_count": prior or 0,
    }


def get_refund_policy(args: PolicyArgs, session: Session) -> list[dict[str, Any]]:
    """Policy is public. No ownership check, nothing customer specific."""
    articles = session.scalars(
        select(Policy).where(Policy.topic == args.topic).order_by(Policy.id)
    ).all()
    if not articles:
        raise ToolRefusal("X4", f"No policy article covers the topic {args.topic}.")
    return [
        {"article_id": a.id, "topic": a.topic, "body": a.body, "version": a.version}
        for a in articles
    ]
