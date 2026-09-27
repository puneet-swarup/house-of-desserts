"""Verify order_detail renders COGS when present."""

from decimal import Decimal

from app.models import MovementReason
from app.services import inventory_service as inv
from app.services import order_service, recipe_service
from app.services.product_service import create_product


def _ingredient(db, name, cost="0.05"):
    return inv.create_ingredient(
        db,
        {
            "name": name,
            "unit": "g",
            "kind": "RAW",
            "cost_per_unit": Decimal(cost),
            "reorder_threshold": Decimal("0"),
        },
    )


def _product(db, sku):
    return create_product(
        db,
        {
            "sku": sku,
            "name": f"Product {sku}",
            "base_price": Decimal("500.00"),
            "gst_rate": Decimal("5.00"),
        },
    )


def test_cogs_renders_on_order_detail(client, db_session, customer):
    ing = _ingredient(db_session, "Flour")
    inv.record_movement(
        db_session,
        ing.id,
        delta=Decimal("1000"),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal("0.50"),
    )

    p = _product(db_session, "COGS-1")
    recipe_service.upsert_recipe_line(db_session, p.id, ing.id, Decimal("100"))

    o = order_service.create_order(
        db_session,
        {
            "customer_id": customer.id,
            "items": [{"product_id": p.id, "quantity": 2}],
            "fulfillment_date": "2026-12-31T12:00",
        },
    )
    order_service.update_status(db_session, o.id, "IN_PROGRESS")

    resp = client.get(f"/orders/{o.id}")
    assert resp.status_code == 200
    # 2 × 100g × ₹0.50 = ₹100
    assert "Ingredient cost" in resp.text
    assert "Gross margin" in resp.text
