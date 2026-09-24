"""Customer model — a person who places orders."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.address import Address
    from app.models.order import Order


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    orders: Mapped[list[Order]] = relationship(
        back_populates="customer", lazy="select"
    )
    addresses: Mapped[list[Address]] = relationship(
        back_populates="customer",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="Address.id",
    )

    __table_args__ = (
        Index(
            "uq_customers_phone_active",
            "phone",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
        Index("ix_customers_is_active", "is_active"),
        Index("ix_customers_name", "name"),
    )

    @property
    def default_address_line(self) -> str:
        """The active address marked default, else the first active one, else empty."""
        actives = [a for a in self.addresses if a.is_active]
        if not actives:
            return ""
        for a in actives:
            if a.is_default:
                return a.line
        return actives[0].line

    def __repr__(self) -> str:
        return f"<Customer id={self.id} name={self.name!r} active={self.is_active}>"
