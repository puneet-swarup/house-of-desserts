"""
ProductIngredient — recipe BOM. How much of one ingredient is needed
for one unit of a product SKU.

Example:
    Chocolate Truffle 500g uses 250g flour, 100g butter, 3 eggs.
    Each row here is one line of that recipe.

Quantity is expressed in the ingredient's own unit ("g", "ml", "pcs").
The service layer is responsible for unit consistency.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.product import Product


class ProductIngredient(Base):
    __tablename__ = "product_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), nullable=False)

    # How much of the ingredient for ONE unit of the product
    quantity_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    product: Mapped[Product] = relationship(lazy="joined")
    ingredient: Mapped[Ingredient] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("product_id", "ingredient_id", name="uq_product_ingredient"),
        Index("ix_product_ingredients_product", "product_id"),
        Index("ix_product_ingredients_ingredient", "ingredient_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProductIngredient product={self.product_id} "
            f"ingredient={self.ingredient_id} qty={self.quantity_per_unit}>"
        )
