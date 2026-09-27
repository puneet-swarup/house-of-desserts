"""Tests for the repeat-order flow (GET /orders/new?from_order_id=N)."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.services import order_service
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


def _order(db, customer, product, qty=1):
    tz = ZoneInfo(get_settings().business_timezone)
    dt = datetime.now(tz).strftime("%Y-%m-%dT12:00")
    return order_service.create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": qty}],
            "fulfillment_date": dt,
        },
    )


def test_repeat_prefills_customer_and_items(client, db_session, customer):
    p = _product(db_session, "REPEAT-1")
    src = _order(db_session, customer, p, qty=3)

    resp = client.get(f"/orders/new?from_order_id={src.id}")
    assert resp.status_code == 200
    text = resp.text
    # Customer select includes selected attribute on the right option
    assert f'value="{customer.id}"' in text
    # Pre-fill banner shows the source order number
    assert src.order_number in text
    # Quantity 3 should appear in the qty input
    assert 'value="3"' in text


def test_repeat_ignores_cancelled_source(client, db_session, customer):
    p = _product(db_session, "REPEAT-2")
    src = _order(db_session, customer, p, qty=2)
    order_service.update_status(db_session, src.id, "CANCELLED")

    resp = client.get(f"/orders/new?from_order_id={src.id}")
    assert resp.status_code == 200
    # Cancelled source → no pre-fill
    assert src.order_number not in resp.text


def test_repeat_handles_missing_source_gracefully(client, db_session):
    resp = client.get("/orders/new?from_order_id=999999")
    # Should still render the blank form, not 500
    assert resp.status_code == 200
    assert "New Order" in resp.text


def test_no_repeat_param_renders_blank_form(client, db_session):
    resp = client.get("/orders/new")
    assert resp.status_code == 200
    assert "New Order" in resp.text
    # No pre-fill banner
    assert "Repeating items from" not in resp.text
