"""Tests for inventory service — ingredient CRUD and stock movements."""

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import IngredientKind, MovementReason
from app.services import inventory_service as inv


def _mk(db, name="Flour", unit="g", kind="RAW", cost="0.05", threshold="1000"):
    return inv.create_ingredient(
        db,
        {
            "name": name,
            "unit": unit,
            "kind": kind,
            "cost_per_unit": Decimal(cost),
            "reorder_threshold": Decimal(threshold),
        },
    )


# --- CRUD ---


def test_create_ingredient(db):
    ing = _mk(db)
    assert ing.id is not None
    assert ing.name == "Flour"
    assert ing.kind == IngredientKind.RAW


def test_duplicate_name_rejected(db):
    _mk(db, name="Butter")
    with pytest.raises(HTTPException) as ei:
        _mk(db, name="Butter")
    assert ei.value.status_code == 400


def test_update_ingredient(db):
    ing = _mk(db)
    updated = inv.update_ingredient(db, ing.id, {"name": "Wheat Flour"})
    assert updated.name == "Wheat Flour"


def test_soft_delete(db):
    ing = _mk(db)
    inv.delete_ingredient(db, ing.id)
    db.refresh(ing)
    assert ing.is_active is False


def test_deleted_name_can_be_reused(db):
    ing = _mk(db, name="Sugar")
    inv.delete_ingredient(db, ing.id)
    ing2 = _mk(db, name="Sugar")
    assert ing2.id != ing.id


# --- Movements ---


def test_on_hand_starts_at_zero(db):
    ing = _mk(db)
    assert inv.on_hand(db, ing.id) == Decimal("0")


def test_purchase_increases_on_hand(db):
    ing = _mk(db)
    inv.record_movement(
        db,
        ing.id,
        delta=Decimal("5000"),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal("0.05"),
    )
    assert inv.on_hand(db, ing.id) == Decimal("5000")


def test_consumption_decreases_on_hand(db):
    ing = _mk(db)
    inv.record_movement(
        db,
        ing.id,
        delta=Decimal("5000"),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal("0.05"),
    )
    inv.record_movement(db, ing.id, delta=Decimal("-500"), reason=MovementReason.CONSUMPTION)
    assert inv.on_hand(db, ing.id) == Decimal("4500")


def test_wastage_decreases_on_hand(db):
    ing = _mk(db)
    inv.record_movement(
        db,
        ing.id,
        delta=Decimal("1000"),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal("0.05"),
    )
    inv.record_movement(db, ing.id, delta=Decimal("-200"), reason=MovementReason.WASTAGE)
    assert inv.on_hand(db, ing.id) == Decimal("800")


def test_purchase_must_be_positive(db):
    ing = _mk(db)
    with pytest.raises(HTTPException) as ei:
        inv.record_movement(db, ing.id, delta=Decimal("-100"), reason=MovementReason.PURCHASE)
    assert ei.value.status_code == 400


def test_consumption_must_be_negative(db):
    ing = _mk(db)
    with pytest.raises(HTTPException) as ei:
        inv.record_movement(db, ing.id, delta=Decimal("100"), reason=MovementReason.CONSUMPTION)
    assert ei.value.status_code == 400


def test_zero_delta_rejected(db):
    ing = _mk(db)
    with pytest.raises(HTTPException):
        inv.record_movement(db, ing.id, delta=Decimal("0"), reason=MovementReason.ADJUSTMENT)


# --- Weighted-average cost ---


def test_purchase_updates_weighted_average_cost(db):
    ing = _mk(db, cost="0.05", threshold="0")
    # Buy 1000 @ 0.05 → cost stays 0.05
    inv.record_movement(
        db,
        ing.id,
        delta=Decimal("1000"),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal("0.05"),
    )
    db.refresh(ing)
    assert ing.cost_per_unit == Decimal("0.05")

    # Buy 1000 @ 0.10 → weighted avg = (1000*0.05 + 1000*0.10) / 2000 = 0.075
    inv.record_movement(
        db,
        ing.id,
        delta=Decimal("1000"),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal("0.10"),
    )
    db.refresh(ing)
    assert ing.cost_per_unit == Decimal("0.075")


def test_consumption_does_not_change_cost(db):
    ing = _mk(db, cost="0.05", threshold="0")
    inv.record_movement(
        db,
        ing.id,
        delta=Decimal("1000"),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal("0.05"),
    )
    db.refresh(ing)
    cost_before = ing.cost_per_unit

    inv.record_movement(db, ing.id, delta=Decimal("-100"), reason=MovementReason.CONSUMPTION)
    db.refresh(ing)
    assert ing.cost_per_unit == cost_before


def test_movement_snapshots_cost(db):
    """The movement stores its own unit_cost/total_cost, immune to later changes."""
    ing = _mk(db, cost="0.05", threshold="0")
    m = inv.record_movement(
        db,
        ing.id,
        delta=Decimal("1000"),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal("0.05"),
    )
    assert m.unit_cost_at_time == Decimal("0.05")
    assert m.total_cost_at_time == Decimal("50")

    # Change ingredient cost later
    inv.update_ingredient(db, ing.id, {"cost_per_unit": Decimal("0.99")})

    db.refresh(m)
    assert m.unit_cost_at_time == Decimal("0.05")  # unchanged
    assert m.total_cost_at_time == Decimal("50")


# --- Batch stock ---


def test_stocks_for_returns_all_ids(db):
    a = _mk(db, name="A")
    b = _mk(db, name="B")
    inv.record_movement(
        db,
        a.id,
        delta=Decimal("100"),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal("0.01"),
    )
    stocks = inv.stocks_for(db, [a.id, b.id])
    assert stocks[a.id] == Decimal("100")
    assert stocks.get(b.id, Decimal("0")) == Decimal("0")


# --- Low stock ---


def test_low_stock_detection(db):
    ing = _mk(db, threshold="1000")
    assert inv.is_low_stock(ing, Decimal("500")) is True
    assert inv.is_low_stock(ing, Decimal("1000")) is True
    assert inv.is_low_stock(ing, Decimal("1001")) is False
