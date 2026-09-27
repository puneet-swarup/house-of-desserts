"""Tests for customer_stats aggregate."""

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models import MovementReason
from app.services import customer_service, order_service, recipe_service
from app.services import inventory_service as inv
from app.services.product_service import create_product


def _product(db, sku, price="500.00"):
    return create_product(
        db,
        {
            "sku": sku,
            "name": f"Product {sku}",
            "base_price": Decimal(price),
            "gst_rate": Decimal("5.00"),
        },
    )


def _order(db, customer, product, qty=1, day_offset=0, advance=0):
    tz = ZoneInfo(get_settings().business_timezone)
    dt = datetime.now(tz) + timedelta(days=day_offset)
    return order_service.create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": qty}],
            "fulfillment_date": dt.strftime("%Y-%m-%dT%H:%M"),
            "advance_paid": advance,
        },
    )


def test_stats_empty_customer(db, customer):
    stats = customer_service.customer_stats(db, customer.id)
    assert stats["order_count"] == 0
    assert stats["cancelled_count"] == 0
    assert stats["lifetime_value"] == Decimal("0.00")
    assert stats["average_order_value"] == Decimal("0.00")
    assert stats["first_order_date"] is None


def test_stats_single_order(db, customer):
    p = _product(db, "STATS-1")
    _order(db, customer, p, qty=1)  # ₹500 + 5% GST = ₹525

    stats = customer_service.customer_stats(db, customer.id)
    assert stats["order_count"] == 1
    assert stats["lifetime_value"] == Decimal("525.00")
    assert stats["average_order_value"] == Decimal("525.00")


def test_stats_multiple_orders_aggregate(db, customer):
    p = _product(db, "STATS-2")
    _order(db, customer, p, qty=1)  # 525
    _order(db, customer, p, qty=2)  # 1050

    stats = customer_service.customer_stats(db, customer.id)
    assert stats["order_count"] == 2
    assert stats["lifetime_value"] == Decimal("1575.00")
    assert stats["average_order_value"] == Decimal("787.50")


def test_stats_excludes_cancelled_orders(db, customer):
    p = _product(db, "STATS-3")
    _order(db, customer, p, qty=1)
    o2 = _order(db, customer, p, qty=5)
    order_service.update_status(db, o2.id, "CANCELLED")

    stats = customer_service.customer_stats(db, customer.id)
    assert stats["order_count"] == 1
    assert stats["cancelled_count"] == 1
    # Only o1's total counted
    assert stats["lifetime_value"] == Decimal("525.00")


def test_stats_outstanding_tracks_unpaid_balance(db, customer):
    p = _product(db, "STATS-4")
    _order(db, customer, p, qty=1, advance=100)  # Total 525, paid 100, balance 425

    stats = customer_service.customer_stats(db, customer.id)
    assert stats["outstanding"] == Decimal("425.00")
    assert stats["collected"] == Decimal("100.00")


def test_stats_outstanding_zero_when_fully_paid(db, customer):
    p = _product(db, "STATS-5")
    _order(db, customer, p, qty=1, advance=525)

    stats = customer_service.customer_stats(db, customer.id)
    assert stats["outstanding"] == Decimal("0.00")
    assert stats["collected"] == Decimal("525.00")


def test_stats_first_and_last_order_dates(db, customer):
    p = _product(db, "STATS-6")
    _order(db, customer, p, day_offset=0)
    _order(db, customer, p, day_offset=5)

    stats = customer_service.customer_stats(db, customer.id)
    assert stats["first_order_date"] is not None
    assert stats["last_order_date"] is not None
    # last is at least as recent as first
    assert stats["last_order_date"] >= stats["first_order_date"]
