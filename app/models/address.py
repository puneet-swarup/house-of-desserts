"""
Address model — a customer can have multiple addresses.
Soft delete: is_active=False instead of removing the row.
"""

from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False, default="Home")
    line: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    customer: Mapped["Customer"] = relationship(back_populates="addresses")

    def __repr__(self) -> str:
        return f"<Address id={self.id} customer={self.customer_id} label={self.label!r} active={self.is_active}>"