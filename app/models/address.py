"""Address model — a customer can have multiple addresses."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.customer import Customer


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False, default="Home")
    line: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    customer: Mapped[Customer] = relationship(back_populates="addresses")

    __table_args__ = (
        Index("ix_addresses_customer_id", "customer_id"),
        Index("ix_addresses_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Address id={self.id} customer={self.customer_id} label={self.label!r}>"
