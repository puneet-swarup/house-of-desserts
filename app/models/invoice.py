"""Invoice model — an IMMUTABLE snapshot of an order at the moment of issue."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.order import Order


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)

    invoice_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    invoice_date: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="ISSUED")

    business_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    business_address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    business_phone: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    business_email: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    business_gstin: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    business_fssai: Mapped[str] = mapped_column(String(20), nullable=False, default="")

    billed_to_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    billed_to_phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    billed_to_email: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    billed_to_address: Mapped[str] = mapped_column(Text, nullable=False, default="")

    order_number: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    order_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    fulfillment_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    delivery_type: Mapped[str] = mapped_column(String(10), nullable=False, default="PICKUP")
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False, default="")

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    gst_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    advance_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    balance_due: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )

    line_items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    pdf_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    order: Mapped[Order] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_invoices_order_id", "order_id"),
        Index("ix_invoices_invoice_date", "invoice_date"),
    )

    def __repr__(self) -> str:
        return f"<Invoice id={self.id} number={self.invoice_number!r} status={self.status}>"
