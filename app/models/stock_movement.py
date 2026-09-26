"""
StockMovement — append-only ledger of every stock change.

Never updated, never deleted. Every received purchase, every consumption
on an order, every wastage, every manual adjustment is a row here.

The `on_hand` quantity of an ingredient is `SUM(delta)` over its
movements. Cost of goods for an order is `SUM(total_cost_at_time)`
over movements where reference points to that order.

The cost columns capture the ingredient's cost at the moment of the
movement, so historical COGS never changes even if purchase prices
later move.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient


class MovementReason(str, enum.Enum):
    PURCHASE = "PURCHASE"  # stock received from supplier  (+)
    CONSUMPTION = "CONSUMPTION"  # used by an order (-)
    WASTAGE = "WASTAGE"  # spoiled, dropped, burned (-)
    RETURN = "RETURN"  # put back after cancelled order (+)
    ADJUSTMENT = "ADJUSTMENT"  # manual correction (+ or -)


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), nullable=False)

    # Positive = stock in, Negative = stock out
    delta: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    reason: Mapped[MovementReason] = mapped_column(SAEnum(MovementReason), nullable=False)

    # Optional reference — e.g. reference_type="Order", reference_id=42
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Snapshot of cost at the time of this movement. Never recomputed.
    unit_cost_at_time: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0.0000")
    )
    total_cost_at_time: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0.0000")
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    ingredient: Mapped[Ingredient] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_stock_movements_ingredient", "ingredient_id", "created_at"),
        Index("ix_stock_movements_reference", "reference_type", "reference_id"),
        Index("ix_stock_movements_reason", "reason"),
    )

    def __repr__(self) -> str:
        return (
            f"<StockMovement id={self.id} ingredient={self.ingredient_id} "
            f"delta={self.delta} reason={self.reason.value}>"
        )
