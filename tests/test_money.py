"""Money math: Decimal rounding, GST split, totals."""

from decimal import Decimal

from app.utils.money import gst_for_line, line_total_with_gst, money, split_gst


def test_money_rounds_half_up():
    assert money("0.005") == Decimal("0.01")
    assert money("0.004") == Decimal("0.00")
    assert money(0.1 + 0.2) == Decimal("0.30")   # not 0.30000000000000004


def test_gst_per_line_rounding():
    # 99.99 * 1 * 5% = 4.9995 -> 5.00 half-up
    assert gst_for_line(Decimal("99.99"), 1, Decimal("5.00")) == Decimal("5.00")


def test_line_total_with_gst():
    gst = gst_for_line(Decimal("99.99"), 3, Decimal("5.00"))
    total = line_total_with_gst(Decimal("99.99"), 3, gst)
    # 99.99 * 3 = 299.97; gst = 14.9985 -> 15.00; total = 314.97
    assert gst == Decimal("15.00")
    assert total == Decimal("314.97")


def test_split_gst_even_and_odd():
    c, s = split_gst(Decimal("15.00"))
    assert c == Decimal("7.50") and s == Decimal("7.50")
    c, s = split_gst(Decimal("15.01"))
    assert c + s == Decimal("15.01")
    assert c == Decimal("7.51")  # half-up
    assert s == Decimal("7.50")


def test_order_totals_via_service(db, customer, product):
    from app.services.order_service import create_order
    order = create_order(db, {
        "customer_id": customer.id,
        "items": [{"product_id": product.id, "quantity": 3}],
        "advance_paid": 100.00,
    })
    assert order.total_amount == Decimal("314.97")
    assert order.advance_paid == Decimal("100.00")
    assert order.balance_due == Decimal("214.97")
    assert order.items[0].gst_amount == Decimal("15.00")
