"""Order and invoice numbers: sequential, unique, gapless under retry."""


import pytest

from app.models import Order
from app.services.numbering import next_order_number
from app.services.order_service import create_order


def test_order_numbers_sequential(db):
    n1 = next_order_number(db)
    db.commit()
    n2 = next_order_number(db)
    db.commit()
    assert n1.endswith("0001")
    assert n2.endswith("0002")
    assert n1 != n2


def test_invoice_number_gapless(db, customer, product):
    from app.services.invoice_service import create_invoice
    o1 = create_order(db, {"customer_id": customer.id,
                           "items": [{"product_id": product.id, "quantity": 1}]})
    o2 = create_order(db, {"customer_id": customer.id,
                           "items": [{"product_id": product.id, "quantity": 1}]})
    i1 = create_invoice(db, o1.id)
    i2 = create_invoice(db, o2.id)
    assert i1.invoice_number.endswith("0001")
    assert i2.invoice_number.endswith("0002")


def test_duplicate_order_number_rejected(db, customer, product):
    from sqlalchemy.exc import IntegrityError
    o = create_order(db, {"customer_id": customer.id,
                          "items": [{"product_id": product.id, "quantity": 1}]})
    dup = Order(order_number=o.order_number, customer_id=customer.id)
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
