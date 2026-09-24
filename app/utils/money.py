"""
Money helpers. Every monetary value in the app is a Decimal quantized
to 2 places using ROUND_HALF_UP.

Rule: never call round() on money. Always use money().
Rule: never sum Floats. Convert to Decimal first.
"""

from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")
HUNDRED = Decimal("100")


def money(value) -> Decimal:
    """
    Convert any numeric input to a Decimal quantized to 2 places,
    rounding half-up. None becomes 0.00.
    """
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    # str() first to avoid float binary artifacts (0.1 -> '0.1', not 0.1000000000000000055)
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def gst_for_line(unit_price: Decimal, qty: int, gst_rate: Decimal) -> Decimal:
    """
    GST for a single line, rounded half-up to 2 places.
    Policy: per-line rounding. The sum of line GST may differ from
    subtotal * rate by a few paise; that is expected and correct for
    Indian GST filing.
    """
    return money(unit_price * Decimal(qty) * gst_rate / HUNDRED)


def line_total_with_gst(unit_price: Decimal, qty: int, gst_amount: Decimal) -> Decimal:
    """Line total = (unit_price * qty) + gst_amount, both Decimal."""
    return money(unit_price * Decimal(qty) + gst_amount)


def split_gst(gst_total: Decimal) -> tuple[Decimal, Decimal]:
    """Split GST into CGST and SGST, half each, half-up."""
    half = money(gst_total / Decimal("2"))
    return half, gst_total - half
