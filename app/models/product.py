"""
Product model — a sellable item (cake, bread, cookie, etc.)
"""

from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # SKU: Your internal stock-keeping unit (e.g., "CHOC-TRUFFLE-500G")
    sku: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    # HSN: Harmonized System code for GST (e.g., "1905" for cakes)
    hsn_code: Mapped[str] = mapped_column(String(10), nullable=False, default="1905")

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Category: "Cake" | "Bread" | "Cookie" | "Pastry" | "Custom"
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="Cake")

    # Pricing
    base_price: Mapped[float] = mapped_column(Float, nullable=False)

    # GST rate for this product (5.0 for most baked goods)
    gst_rate: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)

    # Prep time in hours (for scheduling)
    prep_time_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=4)

    # Active flag — soft delete (set to False instead of deleting)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} sku={self.sku!r} name={self.name!r}>"   