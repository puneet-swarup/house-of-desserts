"""
Pydantic schemas for Product.
"""

from decimal import Decimal

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sku: str = Field(default="", max_length=50)  # optional — auto-generated if blank
    category: str = Field(default="Cake", max_length=50)
    measure_value: Decimal | None = Field(default=None, ge=0)
    measure_unit: str | None = Field(default=None, max_length=10)
    pack_size: int = Field(default=1, ge=1, le=1000)
    pack_label: str = Field(default="", max_length=50)
    base_price: Decimal = Field(..., ge=0)
    gst_rate: Decimal = Field(default=Decimal("5.00"), ge=0, le=28)
    prep_time_hours: int = Field(default=4, ge=0)
    description: str | None = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    sku: str | None = Field(None, max_length=50)
    category: str | None = Field(None, max_length=50)
    measure_value: Decimal | None = Field(None, ge=0)
    measure_unit: str | None = Field(None, max_length=10)
    pack_size: int | None = Field(None, ge=1, le=1000)
    pack_label: str | None = Field(None, max_length=50)
    base_price: Decimal | None = Field(None, ge=0)
    gst_rate: Decimal | None = Field(None, ge=0, le=28)
    prep_time_hours: int | None = Field(None, ge=0)
    description: str | None = None
    is_active: bool | None = None
