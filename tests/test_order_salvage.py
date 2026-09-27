"""Tests for the cancel-from-IN_PROGRESS salvage flow."""

from decimal import Decimal

from app.models import MovementReason, StockMovement
from app.services import inventory_service as inv
from app.services import order_service, recipe_service
from app.services.product_service import create_product


def _ingredient(db, name, cost="0.50"):
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


def _stock(db, ing, qty, cost="0.50"):
    inv.record_movement(
        db,
        ing.id,
        delta=Decimal(str(qty)),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal(str(cost)),
    )


def _in_progress_order(db, customer, product, qty=2):
    o = order_service.create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": qty}],
            "fulfillment_date": "2026-12-31T12:00",
        },
    )
    order_service.update_status(db, o.id, "IN_PROGRESS")
    return o


def test_cancel_with_salvage_restores_stock(db, customer):
    ing = _ingredient(db, "Flour")
    _stock(db, ing, 5000, cost="0.50")
    p = _product(db, "SALV-1")
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("100"))

    o = _in_progress_order(db, customer, p, qty=2)
    db.expire_all()
    assert inv.on_hand(db, ing.id) == Decimal("4800")  # 5000 - 200

    order_service.update_status(db, o.id, "CANCELLED", salvage=True)
    db.expire_all()
    assert inv.on_hand(db, ing.id) == Decimal("5000")


def test_cancel_without_salvage_keeps_stock_deducted(db, customer):
    ing = _ingredient(db, "Butter")
    _stock(db, ing, 5000)
    p = _product(db, "SALV-2")
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("100"))

    o = _in_progress_order(db, customer, p, qty=2)
    order_service.update_status(db, o.id, "CANCELLED", salvage=False)

    db.expire_all()
    assert inv.on_hand(db, ing.id) == Decimal("4800")


def test_cogs_zero_after_salvaged_cancel(db, customer):
    ing = _ingredient(db, "Cocoa", cost="0.80")
    _stock(db, ing, 1000, cost="0.80")
    p = _product(db, "SALV-3")
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("100"))

    o = _in_progress_order(db, customer, p, qty=2)
    # Before cancel: 2 × 100g × 0.80 = ₹160
    assert order_service.order_cogs(db, o.id) == Decimal("160.00")

    order_service.update_status(db, o.id, "CANCELLED", salvage=True)
    assert order_service.order_cogs(db, o.id) == Decimal("0.00")


def test_cogs_persists_after_wasted_cancel(db, customer):
    ing = _ingredient(db, "Sugar", cost="0.40")
    _stock(db, ing, 1000, cost="0.40")
    p = _product(db, "SALV-4")
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("50"))

    o = _in_progress_order(db, customer, p, qty=2)
    # 2 × 50g × 0.40 = ₹40
    order_service.update_status(db, o.id, "CANCELLED", salvage=False)
    assert order_service.order_cogs(db, o.id) == Decimal("40.00")


def test_return_movements_reference_the_order(db, customer):
    ing = _ingredient(db, "Ref Item")
    _stock(db, ing, 1000)
    p = _product(db, "SALV-5")
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("100"))

    o = _in_progress_order(db, customer, p, qty=1)
    order_service.update_status(db, o.id, "CANCELLED", salvage=True)

    db.expire_all()
    returns = (
        db.query(StockMovement)
        .filter_by(
            reference_type="Order",
            reference_id=o.id,
            reason=MovementReason.RETURN,
        )
        .all()
    )
    assert len(returns) == 1
    assert returns[0].delta == Decimal("100")
    assert returns[0].unit_cost_at_time == Decimal("0.50")


def test_salvage_on_confirmed_cancel_does_nothing_extra(db, customer):
    """Cancel from CONFIRMED: no consumption happened, so no returns either."""
    ing = _ingredient(db, "Untouched")
    _stock(db, ing, 1000)
    p = _product(db, "SALV-6")
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("100"))

    o = order_service.create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": p.id, "quantity": 1}],
            "fulfillment_date": "2026-12-31T12:00",
        },
    )
    order_service.update_status(db, o.id, "CANCELLED", salvage=True)

    db.expire_all()
    assert inv.on_hand(db, ing.id) == Decimal("1000")
    assert db.query(StockMovement).filter_by(reference_type="Order", reference_id=o.id).count() == 0
