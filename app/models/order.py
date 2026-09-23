"""
Order and OrderItem models.

An Order belongs to a Customer and contains one or more OrderItems.
This is a classic one-to-many relationship.
"""

from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class OrderStatus(str, enum.Enum):
    """
    Python concept: An Enum is a fixed set of named values.
    By inheriting from both `str` and `enum.Enum`, the values are
    also valid strings (so "CONFIRMED" == OrderStatus.CONFIRMED).
    This lets SQLAlchemy store it as a VARCHAR in SQLite.
    """
    INQUIRY = "INQUIRY"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    DELIVERED = "DELIVERED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Human-readable order number (e.g., "HOD-2026-0001")
    order_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False
    )

    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus), nullable=False, default=OrderStatus.INQUIRY
    )

    # Dates
    order_date: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Delivery info
    delivery_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default="PICKUP"  # "PICKUP" or "DELIVERY"
    )
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Financial summary (denormalized for quick dashboard queries)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    advance_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    balance_due: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(
        back_populates="orders", lazy="joined"
    )
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", lazy="selectin", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Order id={self.id} number={self.order_number!r} status={self.status}>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    gst_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    line_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Customization: "Extra chocolate on top", "No nuts", etc.
    customization_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(lazy="joined")

    def __repr__(self) -> str:
        return f"<OrderItem id={self.id} product={self.product.sku!r} qty={self.quantity}>"   