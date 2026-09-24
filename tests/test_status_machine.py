"""Status transitions: only legal ones allowed."""

import pytest
from fastapi import HTTPException

from app.models import OrderStatus
from app.services.order_service import create_order, update_status


def _new_order(db, customer, product, advance=0):
    return create_order(db, {
        "customer_id": customer.id,
        "fulfillment_date": "2026-12-31T12:00",
        "items": [{"product_id": product.id, "quantity": 1}],
        "advance_paid": advance,
    })


def test_legal_transition(db, customer, product):
    o = _new_order(db, customer, product)
    o = update_status(db, o.id, "IN_PROGRESS")
    assert o.status == OrderStatus.IN_PROGRESS
    o = update_status(db, o.id, "READY")
    assert o.status == OrderStatus.READY


def test_illegal_transition_rejected(db, customer, product):
    o = _new_order(db, customer, product)
    update_status(db, o.id, "CANCELLED")
    with pytest.raises(HTTPException) as ei:
        update_status(db, o.id, "IN_PROGRESS")
    assert ei.value.status_code == 400


def test_paid_is_terminal(db, customer, product):
    o = _new_order(db, customer, product)
    o = update_status(db, o.id, "IN_PROGRESS")
    o = update_status(db, o.id, "READY")
    o = update_status(db, o.id, "DELIVERED")
    o = update_status(db, o.id, "PAID")
    with pytest.raises(HTTPException):
        update_status(db, o.id, "INQUIRY")


def test_bad_status_value(db, customer, product):
    o = _new_order(db, customer, product)
    with pytest.raises(HTTPException) as ei:
        update_status(db, o.id, "BOGUS")
    assert ei.value.status_code == 400
