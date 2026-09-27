"""Unit conversion for inventory and recipe quantities.

Groups:
  MASS   — g, kg      (base: g)
  VOLUME — ml, l      (base: ml)
  COUNT  — pcs, packets, and any other unit are each their own group.

Conversion is only allowed within a group. Unknown units act as their
own singleton group, so they only match themselves.

The COUNT "group" is a category, not a convertible group: `pcs` and
`packets` are compatible only with themselves. There is no implicit
"1 packet = 6 pcs" — that is a product-specific fact (see the pack_size
field on Product) and does not belong in unit conversion.
"""

from decimal import Decimal

from fastapi import HTTPException

MASS = "MASS"
VOLUME = "VOLUME"
# Sentinel only — not used as a group. Each count unit forms its own group.
COUNT = "COUNT"

_TO_BASE: dict[str, Decimal] = {
    "g": Decimal("1"),
    "kg": Decimal("1000"),
    "ml": Decimal("1"),
    "l": Decimal("1000"),
}

# Only units that participate in a real conversion appear here.
# Anything not in this dict falls through to a per-unit unique group
# (see group_of below), which is how pcs, packets, and future units
# stay self-only.
_GROUP: dict[str, str] = {
    "g": MASS,
    "kg": MASS,
    "ml": VOLUME,
    "l": VOLUME,
}

# The set of units the UI offers.
ALL_UNITS = ["g", "kg", "ml", "l", "pcs", "packets"]


def normalize(unit: str | None) -> str:
    return (unit or "").strip().lower()


def group_of(unit: str | None) -> str:
    u = normalize(unit)
    return _GROUP.get(u, f"__{u}__")


def are_compatible(a: str | None, b: str | None) -> bool:
    return group_of(a) == group_of(b)


def convert(qty: Decimal, from_unit: str | None, to_unit: str | None) -> Decimal:
    """
    Convert qty from one unit to another. Both units must be in the
    same group, otherwise raises HTTPException(400).
    """
    f = normalize(from_unit)
    t = normalize(to_unit)
    if not f or not t:
        raise HTTPException(status_code=400, detail="Unit is required")
    if f == t:
        return qty
    if not are_compatible(f, t):
        raise HTTPException(
            status_code=400,
            detail=(f"Cannot convert '{from_unit}' to '{to_unit}' — different unit groups"),
        )
    return qty * _TO_BASE[f] / _TO_BASE[t]


def unit_options_for(unit: str | None) -> list[str]:
    """Units the user can pick when the target is stored in `unit`."""
    g = group_of(unit)
    if g == MASS:
        return ["g", "kg"]
    if g == VOLUME:
        return ["ml", "l"]
    return [normalize(unit)] if unit else []
