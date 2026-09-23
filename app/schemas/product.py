"""
Pydantic schemas for Product — used for input validation and output serialization.

Python concept: Pydantic is a validation library. You define a class with
typed fields, and it automatically validates incoming data (from forms/JSON)
and serializes outgoing data. Think of it as a "contract" for your data.
"""

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    """Schema for creating a new product (form input validation)."""
    name: str = Field(..., min_length=1, max_length=200)
    sku: str = Field(..., min_length=1, max_length=50)
    hsn_code: str = Field(default="1905", max_length=10)
    category: str = Field(default="Cake", max_length=50)
    base_price: float = Field(..., ge=0)
    gst_rate: float = Field(default=5.0, ge=0, le=28)
    prep_time_hours: int = Field(default=4, ge=0)
    description: str | None = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    """Schema for updating an existing product. All fields optional."""
    name: str | None = Field(None, min_length=1, max_length=200)
    sku: str | None = Field(None, min_length=1, max_length=50)
    hsn_code: str | None = Field(None, max_length=10)
    category: str | None = Field(None, max_length=50)
    base_price: float | None = Field(None, ge=0)
    gst_rate: float | None = Field(None, ge=0, le=28)
    prep_time_hours: int | None = Field(None, ge=0)
    description: str | None = None
    is_active: bool | None = None   