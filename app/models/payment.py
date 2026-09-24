"""Payment model — one row per payment received against an order."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.order import Order


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="CASH")
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    received_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="payments")

    __table_args__ = (
        Index("ix_payments_order_id", "order_id"),
        Index("ix_payments_received_at", "received_at"),
    )

    def __repr__(self) -> str:
        return f"<Payment id={self.id} amount={self.amount} method={self.method!r}>"
