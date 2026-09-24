"""Proves PRAGMA foreign_keys is on: bad FK must raise."""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import OrderItem


def test_order_item_with_missing_order_rejected(db, product):
    item = OrderItem(
        order_id=999999,
        product_id=product.id,
        quantity=1,
        unit_price=Decimal("10.00"),
        gst_rate=Decimal("5.00"),
        gst_amount=Decimal("0.50"),
        line_total=Decimal("10.50"),
    )
    db.add(item)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_order_with_missing_customer_rejected(db):
    from app.models import Order
    o = Order(order_number="HOD-2026-9999", customer_id=999999)
    db.add(o)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
