"""Database tables. The DB structure the OpsAgent acts on.

Ids are readable strings with a prefix, so a trace or a log line tells you
what you are looking at without a lookup.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Every table inherits from this."""


class OrderStatus(StrEnum):
    PENDING = "pending"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    LOST = "lost"


class ItemCondition(StrEnum):
    GOOD = "good"
    DAMAGED = "damaged"
    MISSING = "missing"


class RefundStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # The hash of the API key, never the key itself.
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scope: Mapped[str] = mapped_column(String(16), server_default="read")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(String(16))
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    payment_method: Mapped[str] = mapped_column(String(32))

    __table_args__ = (
        CheckConstraint("total_minor > 0", name="ck_orders_total_positive"),
        # A delivered order must know when it was delivered, because the
        # 30 day window is measured from that date.
        CheckConstraint(
            "(status <> 'delivered') OR (delivered_at IS NOT NULL)",
            name="ck_orders_delivered_has_date",
        ),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    sku: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_minor: Mapped[int] = mapped_column(Integer)
    condition: Mapped[ItemCondition] = mapped_column(String(16))
    refundable: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_items_quantity_positive"),
        CheckConstraint("unit_price_minor >= 0", name="ck_items_price_non_negative"),
    )


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[RefundStatus] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_refunds_amount_positive"),
        # The same key can never create a second refund on the same order.
        # This is what makes a retry safe.
        UniqueConstraint(
            "order_id", "idempotency_key", name="uq_refunds_order_idempotency"
        ),
    )


class Policy(Base):
    __tablename__ = "policies"

    # The article id the agent must cite, e.g. "REF-101".
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    topic: Mapped[str] = mapped_column(String(64), index=True)
    body: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tool: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[str] = mapped_column(Text)
    allowed: Mapped[bool] = mapped_column(Boolean)
    # Why it was refused, when it was.
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
