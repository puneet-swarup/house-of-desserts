"""
Payment model — records each payment received against an order.
An order can have multiple payments (advance + balance, or split payments).
"""

from datetime import datetime

from sqlalchemy import String, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"), nullable=False
    )

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="CASH"  # CASH | UPI | BANK | CARD
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # e.g., UPI transaction ID, cheque number, etc.

    received_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    # Relationship
    order: Mapped["Order"] = relationship(back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment id={self.id} amount={self.amount} method={self.method!r}>"   