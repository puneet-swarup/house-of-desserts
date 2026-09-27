"""Tests for order-driven inventory deduction."""

from decimal import Decimal

from app.models import MovementReason, StockMovement
from app.services import inventory_service as inv
from app.services import order_service, recipe_service
from app.services.product_service import create_product


def _ingredient(db, name, unit="g", cost="0.05"):
    return inv.create_ingredient(
        db,
        {
            "name": name,
            "unit": unit,
            "kind": "RAW",
            "reorder_threshold": Decimal("0"),
        },
    )


def _product(db, sku, name="Test Product"):
    return create_product(
        db,
        {
            "sku": sku,
            "name": name,
            "base_price": Decimal("500.00"),
            "gst_rate": Decimal("5.00"),
        },
    )


def _stock(db, ing, qty, cost="0.05"):
    inv.record_movement(
        db,
        ing.id,
        delta=Decimal(str(qty)),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal(str(cost)),
    )


def _order(db, customer, product, qty=1):
    return order_service.create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": qty}],
            "fulfillment_date": "2026-12-31T12:00",
        },
    )


def test_transition_to_in_progress_deducts(db, customer):
    p = _product(db, "CAKE-1")
    ing = _ingredient(db, "Flour")
    _stock(db, ing, 1000)
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("200"))

    o = _order(db, customer, p, qty=1)
    order_service.update_status(db, o.id, "IN_PROGRESS")

    db.expire_all()
    # 200g consumed
    assert inv.on_hand(db, ing.id) == Decimal("800")


def test_deduction_scales_with_quantity(db, customer):
    p = _product(db, "CAKE-2")
    ing = _ingredient(db, "Butter")
    _stock(db, ing, 1000)
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("100"))

    o = _order(db, customer, p, qty=3)
    order_service.update_status(db, o.id, "IN_PROGRESS")

    db.expire_all()
    # 3 × 100g = 300g consumed
    assert inv.on_hand(db, ing.id) == Decimal("700")


def test_deduction_aggregates_across_items(db, customer):
    """Two products share an ingredient — both consumptions sum."""
    p1 = _product(db, "P-1")
    p2 = _product(db, "P-2")
    ing = _ingredient(db, "Sugar")
    _stock(db, ing, 1000)
    recipe_service.upsert_recipe_line(db, p1.id, ing.id, Decimal("50"))
    recipe_service.upsert_recipe_line(db, p2.id, ing.id, Decimal("30"))

    o = order_service.create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [
                {"product_id": p1.id, "quantity": 2},  # 100g
                {"product_id": p2.id, "quantity": 1},  # 30g
            ],
            "fulfillment_date": "2026-12-31T12:00",
        },
    )
    order_service.update_status(db, o.id, "IN_PROGRESS")

    db.expire_all()
    assert inv.on_hand(db, ing.id) == Decimal("870")


def test_no_recipe_no_deduction(db, customer):
    p = _product(db, "PLAIN")
    ing = _ingredient(db, "Unused")
    _stock(db, ing, 500)

    o = _order(db, customer, p)
    order_service.update_status(db, o.id, "IN_PROGRESS")

    db.expire_all()
    assert inv.on_hand(db, ing.id) == Decimal("500")
    assert db.query(StockMovement).filter_by(reason=MovementReason.CONSUMPTION).count() == 0


def test_shortage_does_not_block_transition(db, customer):
    p = _product(db, "SHORT")
    ing = _ingredient(db, "Scarce")
    _stock(db, ing, 50)
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("200"))

    o = _order(db, customer, p)
    order_service.update_status(db, o.id, "IN_PROGRESS")

    db.expire_all()
    # Stock went negative — allowed
    assert inv.on_hand(db, ing.id) == Decimal("-150")
    db.refresh(o)
    assert o.status.value == "IN_PROGRESS"


def test_shortage_check_reports_shortfalls(db, customer):
    p = _product(db, "CHECK")
    ing = _ingredient(db, "Rice")
    _stock(db, ing, 100)
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("250"))

    o = _order(db, customer, p)
    shortages = order_service.check_production_shortages(db, o.id)

    assert len(shortages) == 1
    assert shortages[0]["ingredient"].id == ing.id
    assert shortages[0]["needed"] == Decimal("250")
    assert shortages[0]["on_hand"] == Decimal("100")
    assert shortages[0]["shortfall"] == Decimal("150")


def test_shortage_check_empty_when_stock_sufficient(db, customer):
    p = _product(db, "OK-STOCK")
    ing = _ingredient(db, "Plenty")
    _stock(db, ing, 1000)
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("100"))

    o = _order(db, customer, p)
    assert order_service.check_production_shortages(db, o.id) == []


def test_order_cogs_sums_consumption(db, customer):
    p = _product(db, "COGS")
    ing = _ingredient(db, "Cocoa")
    _stock(db, ing, 500, cost="0.50")  # ₹0.50/g
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("100"))

    o = _order(db, customer, p, qty=2)
    order_service.update_status(db, o.id, "IN_PROGRESS")

    db.expire_all()
    # 2 × 100g × 0.50 = ₹100
    assert order_service.order_cogs(db, o.id) == Decimal("100.00")


def test_order_cogs_zero_when_no_recipe(db, customer):
    p = _product(db, "NO-RCP")
    o = _order(db, customer, p)
    order_service.update_status(db, o.id, "IN_PROGRESS")
    assert order_service.order_cogs(db, o.id) == Decimal("0.00")


def test_cogs_cost_snapshot_immune_to_price_change(db, customer):
    """COGS uses the cost at consumption time, not the current cost."""
    p = _product(db, "SNAP")
    ing = _ingredient(db, "Snapshot")
    _stock(db, ing, 500, cost="0.50")
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("100"))

    o = _order(db, customer, p, qty=1)
    order_service.update_status(db, o.id, "IN_PROGRESS")

    # Now prices double
    _stock(db, ing, 500, cost="1.00")

    db.expire_all()
    # COGS still at ₹50 (100g × ₹0.50), not ₹100
    assert order_service.order_cogs(db, o.id) == Decimal("50.00")


def test_transition_cancel_from_confirmed_no_deduction(db, customer):
    p = _product(db, "CANCEL-EARLY")
    ing = _ingredient(db, "Untouched")
    _stock(db, ing, 500)
    recipe_service.upsert_recipe_line(db, p.id, ing.id, Decimal("100"))

    o = _order(db, customer, p)
    order_service.update_status(db, o.id, "CANCELLED")

    db.expire_all()
    assert inv.on_hand(db, ing.id) == Decimal("500")
