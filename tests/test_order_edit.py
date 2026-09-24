"""Tests for order editing — CONFIRMED-only guard, total floor, audit."""

import pytest
from fastapi import HTTPException

from app.models import AuditLog, OrderStatus
from app.services.order_service import create_order, update_order
from app.utils.money import money


def _mk_order(db, customer, product, qty=2, advance=0):
    return create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": qty}],
            "fulfillment_date": "2026-12-31T12:00",
            "advance_paid": advance,
        },
    )


def test_edit_confirmed_order_updates_fields(db, customer, product):
    o = _mk_order(db, customer, product)

    updated = update_order(
        db,
        o.id,
        {
            "fulfillment_date": "2027-01-15T15:30",
            "delivery_type": "DELIVERY",
            "delivery_address": "New address, Pune",
            "notes": "Rang the bell twice",
            "items": [{"product_id": product.id, "quantity": 3}],
        },
    )

    assert updated.delivery_type == "DELIVERY"
    assert updated.delivery_address == "New address, Pune"
    assert updated.notes == "Rang the bell twice"
    assert updated.items[0].quantity == 3


def test_edit_recomputes_totals(db, customer, product):
    o = _mk_order(db, customer, product, qty=1)
    original_total = o.total_amount

    updated = update_order(
        db,
        o.id,
        {
            "fulfillment_date": "2026-12-31T12:00",
            "delivery_type": "PICKUP",
            "items": [{"product_id": product.id, "quantity": 4}],
        },
    )

    assert updated.total_amount == money(original_total * 4)
    assert updated.balance_due == updated.total_amount


def test_edit_rejected_when_not_confirmed(db, customer, product):
    o = _mk_order(db, customer, product)
    # Move to IN_PROGRESS — no longer editable
    from app.services.order_service import update_status

    update_status(db, o.id, "IN_PROGRESS")

    with pytest.raises(HTTPException) as ei:
        update_order(
            db,
            o.id,
            {
                "fulfillment_date": "2026-12-31T12:00",
                "items": [{"product_id": product.id, "quantity": 1}],
            },
        )
    assert ei.value.status_code == 400
    assert "CONFIRMED" in ei.value.detail


def test_edit_rejected_when_reducing_below_paid(db, customer, product):
    # Order with advance = 500
    o = _mk_order(db, customer, product, qty=2, advance=200)
    # Total: 2 x 99.99 + 5% GST = ~210; advance 200; balance ~10

    # Try to reduce to 1 unit (~105 total), below the 200 already paid
    with pytest.raises(HTTPException) as ei:
        update_order(
            db,
            o.id,
            {
                "fulfillment_date": "2026-12-31T12:00",
                "items": [{"product_id": product.id, "quantity": 1}],
            },
        )
    assert ei.value.status_code == 400
    assert "below" in ei.value.detail.lower()


def test_edit_writes_audit_entry(db, customer, product):
    o = _mk_order(db, customer, product)
    audit_before = db.query(AuditLog).filter_by(entity_type="Order", action="UPDATE").count()

    update_order(
        db,
        o.id,
        {
            "fulfillment_date": "2026-12-31T12:00",
            "delivery_type": "DELIVERY",
            "delivery_address": "Updated",
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )

    audit_after = db.query(AuditLog).filter_by(entity_type="Order", action="UPDATE").count()
    assert audit_after == audit_before + 1

    entry = (
        db.query(AuditLog)
        .filter_by(entity_type="Order", action="UPDATE")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert "New address" not in (entry.old_value or "")  # sanity
    assert "Updated" in (entry.new_value or "")


def test_edit_requires_fulfillment_date(db, customer, product):
    o = _mk_order(db, customer, product)
    with pytest.raises(HTTPException) as ei:
        update_order(
            db,
            o.id,
            {
                "fulfillment_date": None,
                "items": [{"product_id": product.id, "quantity": 1}],
            },
        )
    assert ei.value.status_code == 400
    assert "Fulfillment" in ei.value.detail


def test_edit_requires_items(db, customer, product):
    o = _mk_order(db, customer, product)
    with pytest.raises(HTTPException) as ei:
        update_order(
            db,
            o.id,
            {
                "fulfillment_date": "2026-12-31T12:00",
                "items": [],
            },
        )
    assert ei.value.status_code == 400
