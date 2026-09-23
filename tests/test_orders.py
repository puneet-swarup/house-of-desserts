"""Tests for order lifecycle, delivery, and payments."""

from app.models import Order, OrderStatus
from datetime import datetime   


def test_create_order_pickup(client, db_session, sample_customer, sample_product):
    client.post("/orders", data={
        "customer_id": str(sample_customer.id),
        "delivery_type": "PICKUP",
        "delivery_date": "",
        "delivery_address": "",
        "notes": "",
        "advance_paid": "0",
        "advance_method": "UPI",
        "product_id": [str(sample_product.id)],
        "quantity": ["1"],
    })
    order = db_session.query(Order).first()
    assert order is not None
    assert order.delivery_type == "PICKUP"
    assert order.delivery_address is None or order.delivery_address == ""


def test_create_order_delivery(client, db_session, sample_customer, sample_product):
    client.post("/orders", data={
        "customer_id": str(sample_customer.id),
        "delivery_type": "DELIVERY",
        "delivery_date": "2026-09-25",
        "delivery_address": "456 Delivery Lane, Pune",
        "notes": "Ring bell twice",
        "advance_paid": "100.00",
        "advance_method": "CASH",
        "product_id": [str(sample_product.id)],
        "quantity": ["2"],
    })
    order = db_session.query(Order).first()
    assert order is not None
    assert order.delivery_type == "DELIVERY"
    assert order.delivery_address == "456 Delivery Lane, Pune"


def test_order_totals_calculated_correctly(client, db_session, sample_customer, sample_product):
    client.post("/orders", data={
        "customer_id": str(sample_customer.id),
        "delivery_type": "PICKUP",
        "delivery_date": "",
        "delivery_address": "",
        "notes": "",
        "advance_paid": "100.00",
        "advance_method": "CASH",
        "product_id": [str(sample_product.id)],
        "quantity": ["2"],
    })
    order = db_session.query(Order).first()
    # 2 x 500 = 1000 subtotal, GST 5% = 50, total = 1050
    assert order.total_amount == 1050.0
    assert order.advance_paid == 100.0
    assert order.balance_due == 950.0


def test_status_transition_forward(client, db_session, sample_order):
    assert sample_order.status == OrderStatus.CONFIRMED
    resp = client.post(f"/orders/{sample_order.id}/status", data={"status": "IN_PROGRESS"})
    assert resp.status_code == 200
    db_session.refresh(sample_order)
    assert sample_order.status == OrderStatus.IN_PROGRESS


def test_full_payment_sets_paid(client, db_session, sample_order):
    assert sample_order.balance_due > 0
    client.post(f"/orders/{sample_order.id}/payments", data={
        "amount": str(sample_order.balance_due),
        "method": "UPI",
        "reference": "TXN123",
    })
    db_session.refresh(sample_order)
    assert sample_order.balance_due == 0
    assert sample_order.status == OrderStatus.PAID


def test_partial_payment_reduces_balance(client, db_session, sample_order):
    old_balance = sample_order.balance_due
    client.post(f"/orders/{sample_order.id}/payments", data={
        "amount": "100.00",
        "method": "CASH",
        "reference": "",
    })
    db_session.refresh(sample_order)
    assert sample_order.balance_due == old_balance - 100.0


def test_cancel_order(client, db_session, sample_order):
    client.post(f"/orders/{sample_order.id}/status", data={"status": "CANCELLED"})
    db_session.refresh(sample_order)
    assert sample_order.status == OrderStatus.CANCELLED


def test_order_list_filter(client, db_session, sample_order):
    client.post(f"/orders/{sample_order.id}/status", data={"status": "IN_PROGRESS"})
    resp = client.get("/orders?status=IN_PROGRESS")
    assert resp.status_code == 200
    assert sample_order.order_number in resp.text


def test_order_detail_shows_delivery_address(client, db_session, sample_order):
    resp = client.get(f"/orders/{sample_order.id}")
    assert resp.status_code == 200
    assert sample_order.order_number in resp.text
    assert "Items" in resp.text
    assert "Payments" in resp.text
    # Delivery address should appear since delivery_type is DELIVERY
    assert "123 Test Street" in resp.text


def test_order_detail_pickup_no_address(client, db_session, sample_customer, sample_product):
    client.post("/orders", data={
        "customer_id": str(sample_customer.id),
        "delivery_type": "PICKUP",
        "delivery_date": "",
        "delivery_address": "",
        "notes": "",
        "advance_paid": "0",
        "advance_method": "UPI",
        "product_id": [str(sample_product.id)],
        "quantity": ["1"],
    })
    order = db_session.query(Order).filter_by(delivery_type="PICKUP").first()
    resp = client.get(f"/orders/{order.id}")
    assert resp.status_code == 200
    # Should NOT show a delivery address section
    assert "Deliver to:" not in resp.text

def test_export_orders_includes_delivery_type(client, db_session, sample_order):
    db_session.expire_all()
    today = datetime.now().strftime("%Y-%m-%d")
    resp = client.get(f"/export/orders.csv?start=2020-01-01&end={today}")
    assert "DELIVERY" in resp.text