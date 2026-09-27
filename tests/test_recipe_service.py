"""Tests for recipe service — BOM, cost, and capacity."""

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.services import inventory_service as inv
from app.services import recipe_service as rs

# --- Helpers ---


def _ingredient(db, name, unit="g", cost="0.05"):
    return inv.create_ingredient(
        db,
        {
            "name": name,
            "unit": unit,
            "kind": "RAW",
            "cost_per_unit": Decimal(cost),
            "reorder_threshold": Decimal("0"),
        },
    )


def _stock(db, ing, qty, cost="0.05"):
    inv.record_movement(
        db,
        ing.id,
        delta=Decimal(str(qty)),
        reason="PURCHASE",
        unit_cost=Decimal(cost),
    )


def _product(db, sku="CAKE-500"):
    from app.services.product_service import create_product

    return create_product(
        db,
        {
            "sku": sku,
            "name": f"Cake {sku}",
            "base_price": Decimal("500.00"),
            "gst_rate": Decimal("5.00"),
        },
    )


# --- list_recipe ---


def test_empty_recipe(db):
    p = _product(db)
    assert rs.list_recipe(db, p.id) == []


def test_add_line(db):
    p = _product(db)
    ing = _ingredient(db, "Flour")

    line = rs.upsert_recipe_line(db, p.id, ing.id, Decimal("250"))
    assert line.quantity_per_unit == Decimal("250")

    lines = rs.list_recipe(db, p.id)
    assert len(lines) == 1


def test_upsert_updates_existing_line(db):
    p = _product(db)
    ing = _ingredient(db, "Sugar")

    rs.upsert_recipe_line(db, p.id, ing.id, Decimal("100"))
    rs.upsert_recipe_line(db, p.id, ing.id, Decimal("150"))

    lines = rs.list_recipe(db, p.id)
    assert len(lines) == 1
    assert lines[0].quantity_per_unit == Decimal("150")


def test_negative_quantity_rejected(db):
    p = _product(db)
    ing = _ingredient(db, "Butter")

    with pytest.raises(HTTPException) as ei:
        rs.upsert_recipe_line(db, p.id, ing.id, Decimal("-5"))
    assert ei.value.status_code == 400


def test_inactive_ingredient_rejected(db):
    p = _product(db)
    ing = _ingredient(db, "Old Ingredient")
    inv.delete_ingredient(db, ing.id)

    with pytest.raises(HTTPException) as ei:
        rs.upsert_recipe_line(db, p.id, ing.id, Decimal("10"))
    assert ei.value.status_code == 400
    assert "inactive" in ei.value.detail.lower()


def test_remove_line(db):
    p = _product(db)
    ing = _ingredient(db, "Cocoa")

    line = rs.upsert_recipe_line(db, p.id, ing.id, Decimal("20"))
    rs.remove_recipe_line(db, line.id)

    assert rs.list_recipe(db, p.id) == []


# --- recipe_cost ---


def test_recipe_cost_sums_ingredient_costs(db):
    p = _product(db)
    flour = _ingredient(db, "Flour")
    butter = _ingredient(db, "Butter")

    # Flour: 250g @ 0.05 = 12.50
    # Butter: 100g @ 0.20 = 20.00
    _stock(db, flour, 1000, cost="0.05")
    _stock(db, butter, 1000, cost="0.20")

    rs.upsert_recipe_line(db, p.id, flour.id, Decimal("250"))
    rs.upsert_recipe_line(db, p.id, butter.id, Decimal("100"))

    assert rs.recipe_cost(db, p.id) == Decimal("32.50")


def test_recipe_cost_with_no_lines_is_zero(db):
    p = _product(db)
    assert rs.recipe_cost(db, p.id) == Decimal("0.00")


# --- capacity ---


def test_capacity_no_recipe_is_none(db):
    p = _product(db)
    cap = rs.capacity_for_product(db, p.id)
    assert cap["has_recipe"] is False
    assert cap["capacity"] is None


def test_capacity_limited_by_smallest_stock(db):
    p = _product(db)
    flour = _ingredient(db, "Flour")
    butter = _ingredient(db, "Butter")

    # Flour: 1000g / 250g per cake = 4 cakes
    # Butter: 500g / 100g per cake = 5 cakes
    # Capacity should be 4, bottleneck = flour
    _stock(db, flour, 1000)
    _stock(db, butter, 500)

    rs.upsert_recipe_line(db, p.id, flour.id, Decimal("250"))
    rs.upsert_recipe_line(db, p.id, butter.id, Decimal("100"))

    cap = rs.capacity_for_product(db, p.id)
    assert cap["capacity"] == 4
    assert cap["bottleneck"].name == "Flour"


def test_capacity_zero_when_ingredient_exhausted(db):
    p = _product(db)
    ing = _ingredient(db, "Scarce")
    rs.upsert_recipe_line(db, p.id, ing.id, Decimal("10"))
    # no stock recorded → capacity 0

    cap = rs.capacity_for_product(db, p.id)
    assert cap["capacity"] == 0


def test_capacity_floors_fractional(db):
    """3.9 cakes → capacity 3."""
    p = _product(db)
    ing = _ingredient(db, "Eggs", unit="pcs")
    _stock(db, ing, 39)  # 39 eggs / 10 per cake = 3.9 → 3
    rs.upsert_recipe_line(db, p.id, ing.id, Decimal("10"))

    cap = rs.capacity_for_product(db, p.id)
    assert cap["capacity"] == 3


def test_capacity_batch(db):
    p1 = _product(db, sku="A")
    p2 = _product(db, sku="B")
    ing = _ingredient(db, "Shared")

    _stock(db, ing, 100)
    rs.upsert_recipe_line(db, p1.id, ing.id, Decimal("10"))  # 10 possible
    rs.upsert_recipe_line(db, p2.id, ing.id, Decimal("25"))  # 4 possible

    caps = rs.capacity_for_products(db, [p1.id, p2.id])
    assert caps[p1.id]["capacity"] == 10
    assert caps[p2.id]["capacity"] == 4


# --- replace_recipe ---


def test_replace_recipe_overwrites(db):
    p = _product(db)
    a = _ingredient(db, "A")
    b = _ingredient(db, "B")
    c = _ingredient(db, "C")

    rs.upsert_recipe_line(db, p.id, a.id, Decimal("1"))
    rs.upsert_recipe_line(db, p.id, b.id, Decimal("2"))

    rs.replace_recipe(
        db,
        p.id,
        [
            {"ingredient_id": c.id, "quantity_per_unit": "5"},
            {"ingredient_id": a.id, "quantity_per_unit": "10"},
        ],
    )

    lines = rs.list_recipe(db, p.id)
    assert len(lines) == 2
    ids = {l.ingredient_id for l in lines}
    assert ids == {a.id, c.id}


def test_replace_recipe_rejects_duplicates(db):
    p = _product(db)
    a = _ingredient(db, "Dup")

    with pytest.raises(HTTPException) as ei:
        rs.replace_recipe(
            db,
            p.id,
            [
                {"ingredient_id": a.id, "quantity_per_unit": "1"},
                {"ingredient_id": a.id, "quantity_per_unit": "2"},
            ],
        )
    assert ei.value.status_code == 400


def test_replace_recipe_empty_clears(db):
    p = _product(db)
    a = _ingredient(db, "Temp")
    rs.upsert_recipe_line(db, p.id, a.id, Decimal("1"))

    rs.replace_recipe(db, p.id, [])
    assert rs.list_recipe(db, p.id) == []

    def test_recipe_line_converts_g_to_kg(db):
        """Ingredient in kg, recipe entered in g — converted on save."""
        p = _product(db)
        # Ingredient stored in kg
        ing = inv.create_ingredient(
            db,
            {
                "name": "Flour (kg)",
                "unit": "kg",
                "kind": "RAW",
                "reorder_threshold": Decimal("0"),
            },
        )

        line = rs.upsert_recipe_line(db, p.id, ing.id, Decimal("500"), from_unit="g")
        # 500 g stored as 0.5 kg
        assert line.quantity_per_unit == Decimal("0.5")

    def test_capacity_after_conversion(db):
        """Stock 5 kg, recipe 500 g → capacity 10."""
        p = _product(db)
        ing = inv.create_ingredient(
            db,
            {
                "name": "Bulk Flour",
                "unit": "kg",
                "kind": "RAW",
                "reorder_threshold": Decimal("0"),
            },
        )
        inv.record_movement(
            db,
            ing.id,
            delta=Decimal("5"),
            reason="PURCHASE",
            unit_cost=Decimal("50"),
        )
        rs.upsert_recipe_line(db, p.id, ing.id, Decimal("500"), from_unit="g")

        cap = rs.capacity_for_product(db, p.id)
        assert cap["capacity"] == 10
