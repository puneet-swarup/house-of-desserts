"""
Invoice model — tracks generated invoices (PDF and/or thermal receipt).
"""

from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"), nullable=False, unique=True
    )

    invoice_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    invoice_date: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    # "DRAFT" | "ISSUED" | "PAID" | "VOID"
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="DRAFT")

    # Path to generated PDF (for records)
    pdf_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Invoice id={self.id} number={self.invoice_number!r} status={self.status}>"   