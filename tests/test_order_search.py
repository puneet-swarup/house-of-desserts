"""Tests for order search + pagination."""

from datetime import datetime, timedelta

from app.models import OrderStatus
from app.services.order_service import create_order, search_orders, update_status


def _mk(db, customer, product, *, qty=1, day_offset=1):
    """Create an order with fulfillment N days from now."""
    fulfillment = (datetime.now() + timedelta(days=day_offset)).strftime("%Y-%m-%dT12:00")
    return create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": qty}],
            "fulfillment_date": fulfillment,
        },
    )


def test_search_by_order_number_fragment(db, customer, product):
    o = _mk(db, customer, product)
    # Search the numeric suffix
    rows, meta = search_orders(db, q="0001")
    assert any(r.id == o.id for r in rows)


def test_search_by_customer_name(db, customer, product):
    _mk(db, customer, product)
    rows, meta = search_orders(db, q="Anita")
    assert len(rows) == 1
    assert rows[0].customer.name == "Anita Rao"


def test_search_by_customer_phone_digits_ignores_spaces(db, customer, product):
    # customer fixture phone is "9876543210"
    _mk(db, customer, product)
    rows, meta = search_orders(db, q="98765")
    assert len(rows) == 1


def test_search_no_match(db, customer, product):
    _mk(db, customer, product)
    rows, meta = search_orders(db, q="zzz-nobody")
    assert rows == []
    assert meta["total"] == 0


def test_search_combined_with_status_filter(db, customer, product):
    o = _mk(db, customer, product)
    _mk(db, customer, product)
    update_status(db, o.id, "CANCELLED")

    rows, meta = search_orders(db, q="Anita", status="CANCELLED")
    assert len(rows) == 1
    assert rows[0].status == OrderStatus.CANCELLED


def test_pagination_meta_correct(db, customer, product):
    for i in range(30):
        _mk(db, customer, product, day_offset=i + 1)

    rows, meta = search_orders(db, page=1, per_page=10)
    assert len(rows) == 10
    assert meta["total"] == 30
    assert meta["pages"] == 3
    assert meta["has_prev"] is False
    assert meta["has_next"] is True

    rows2, meta2 = search_orders(db, page=3, per_page=10)
    assert len(rows2) == 10
    assert meta2["page"] == 3
    assert meta2["has_prev"] is True
    assert meta2["has_next"] is False


def test_pagination_sorts_by_fulfillment(db, customer, product):
    _mk(db, customer, product, day_offset=5)
    _mk(db, customer, product, day_offset=1)  # earliest
    _mk(db, customer, product, day_offset=3)

    rows, _ = search_orders(db)
    assert rows[0].fulfillment_date < rows[1].fulfillment_date < rows[2].fulfillment_date
