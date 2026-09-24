"""
SKU generation and validation.

Convention:
    {BASE}-{MEASURE}{-PACK}

BASE:   first 15 chars of product name, uppercase, non-alphanumeric -> "-", trimmed
MEASURE: value+unit normalized, e.g. 500G, 1KG, 500ML, 1L
PACK:    e.g. 6PK, only if pack_size > 1
COLLISION: append -2, -3, ...
"""

from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product

SLUG_RE = re.compile(r"[^A-Z0-9]+")
BASE_MAX_LEN = 15


def slugify(name: str) -> str:
    """Uppercase alphanumeric slug, hyphens for runs of non-alphanumerics."""
    s = SLUG_RE.sub("-", name.upper()).strip("-")
    s = s[:BASE_MAX_LEN].rstrip("-")
    return s or "PROD"


def normalize_measure(value: Decimal | float | int | None, unit: str | None) -> tuple[Decimal | None, str | None]:
    """
    Normalize (value, unit) to a canonical (value, unit).

    Rules:
      - kg < 1 -> g (multiply by 1000)
      - g >= 1000 -> kg (divide by 1000)
      - l  < 1 -> ml
      - ml >= 1000 -> l
      - Unknown unit stays as-is (lowercased)
    """
    if value is None or not unit:
        return (None, None)
    v = Decimal(str(value))
    u = unit.strip().lower()
    if u == "kg" and v < 1:
        return (v * 1000, "g")
    if u == "g" and v >= 1000:
        return (v / 1000, "kg")
    if u == "l" and v < 1:
        return (v * 1000, "ml")
    if u == "ml" and v >= 1000:
        return (v / 1000, "l")
    return (v, u)


def _format_measure(value: Decimal | None, unit: str | None) -> str | None:
    if value is None or not unit:
        return None
    # Trim trailing zeros: 500.00 -> 500 ; 1.50 -> 1.5
    v = value.normalize()
    # Decimal.normalize() can produce scientific notation for whole numbers
    if v == v.to_integral_value():
        v = v.quantize(Decimal("1"))
    return f"{v}{unit.upper()}"


def base_sku(
    name: str,
    measure_value: Decimal | None = None,
    measure_unit: str | None = None,
    pack_size: int = 1,
) -> str:
    """Build the SKU from parts, without collision handling."""
    parts = [slugify(name)]
    v, u = normalize_measure(measure_value, measure_unit)
    m = _format_measure(v, u)
    if m:
        parts.append(m)
    if pack_size and pack_size > 1:
        parts.append(f"{pack_size}PK")
    return "-".join(parts)


def unique_sku(
    db: Session,
    name: str,
    measure_value: Decimal | None = None,
    measure_unit: str | None = None,
    pack_size: int = 1,
    *,
    exclude_product_id: int | None = None,
) -> str:
    """
    Generate a SKU that does not collide with any existing product.
    Appends -2, -3, ... on collision.
    """
    base = base_sku(name, measure_value, measure_unit, pack_size)
    candidate = base
    counter = 1
    while True:
        q = select(Product).where(Product.sku == candidate)
        if exclude_product_id is not None:
            q = q.where(Product.id != exclude_product_id)
        if db.execute(q).scalar_one_or_none() is None:
            return candidate
        counter += 1
        candidate = f"{base}-{counter}"
        # Defensive: cap at 99 to avoid infinite loop from bad data
        if counter > 99:
            raise RuntimeError(f"Cannot generate a unique SKU based on {base!r}")


def validate_sku_format(sku: str) -> str:
    """Normalize a user-provided SKU: uppercase, hyphens, no leading/trailing."""
    s = SLUG_RE.sub("-", sku.upper()).strip("-")
    if not s:
        raise ValueError("SKU cannot be empty")
    if len(s) > 50:
        s = s[:50].rstrip("-")
    return s
