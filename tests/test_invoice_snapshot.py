"""Invoice is immutable: editing the order must not change the invoice."""

from decimal import Decimal

from app.services.invoice_service import create_invoice
from app.services.order_service import create_order


def test_invoice_snapshot_survives_order_edit(db, customer, product):
    o = create_order(db, {
        "customer_id": customer.id,
        "fulfillment_date": "2026-12-31T12:00",
        "items": [{"product_id": product.id, "quantity": 2}],
    })
    inv = create_invoice(db, o.id)
    frozen_total = inv.total_amount
    frozen_items = inv.line_items_json

    # Now change the product price (affects future orders, not this invoice)
    product.base_price = Decimal("200.00")
    db.commit()

    # Reload invoice — must be unchanged
    db.refresh(inv)
    assert inv.total_amount == frozen_total
    assert inv.line_items_json == frozen_items


def test_invoice_snapshot_survives_customer_rename(db, customer, product):
    o = create_order(db, {
        "customer_id": customer.id,
        "fulfillment_date": "2026-12-31T12:00",
        "items": [{"product_id": product.id, "quantity": 1}],
    })
    inv = create_invoice(db, o.id)
    old_name = inv.billed_to_name

    customer.name = "Renamed Customer"
    db.commit()

    db.refresh(inv)
    assert inv.billed_to_name == old_name
