"""
Ingredient — a raw material or packaging item tracked in inventory.

Units are free-form strings ("g", "kg", "ml", "l", "pcs", "packets")
but the same unit should be used consistently for one ingredient.
Normalization (500g vs 0.5kg) is the user's responsibility — the app
will treat them as different if you enter them differently.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.time import utcnow


class IngredientKind(str, enum.Enum):
    RAW = "RAW"  # flour, butter, eggs
    PACKAGING = "PACKAGING"  # cake boxes, ribbon, stickers


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    kind: Mapped[IngredientKind] = mapped_column(
        SAEnum(IngredientKind),
        nullable=False,
        default=IngredientKind.RAW,
    )

    # Unit for this ingredient — "g", "kg", "ml", "l", "pcs", "packets"
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="g")

    # Current purchase cost per unit. Updated on purchases (weighted
    # average). Never recomputed retrospectively for past movements —
    # movements store their own snapshot.
    cost_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0.0000")
    )

    # Alert when available stock falls at or below this.
    reorder_threshold: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=Decimal("0.000")
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        Index(
            "uq_ingredients_name_active",
            "name",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
        Index("ix_ingredients_is_active", "is_active"),
        Index("ix_ingredients_kind", "kind"),
    )

    def __repr__(self) -> str:
        return f"<Ingredient id={self.id} name={self.name!r} unit={self.unit!r}>"
