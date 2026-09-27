from decimal import Decimal

from app.models import MovementReason
from app.services import inventory_service as inv
from app.services import today_service


def _ingredient(db, name, unit="g", threshold="1000", cost="0.05"):
    return inv.create_ingredient(
        db,
        {
            "name": name,
            "unit": unit,
            "kind": "RAW",
            "cost_per_unit": Decimal(cost),
            "reorder_threshold": Decimal(threshold),
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


def test_low_stock_empty_when_no_ingredients(db):
    assert today_service.low_stock_ingredients(db) == []


def test_low_stock_empty_when_all_above_threshold(db):
    ing = _ingredient(db, "Flour", threshold="1000")
    _stock(db, ing, 5000)
    assert today_service.low_stock_ingredients(db) == []


def test_low_stock_flags_below_threshold(db):
    ing = _ingredient(db, "Sugar", threshold="2000")
    _stock(db, ing, 500)
    rows = today_service.low_stock_ingredients(db)
    assert len(rows) == 1
    assert rows[0]["ingredient"].id == ing.id
    assert rows[0]["on_hand"] == Decimal("500")
    assert rows[0]["shortfall"] == Decimal("1500")


def test_low_stock_sorted_by_shortfall(db):
    small = _ingredient(db, "Small", threshold="500")
    big = _ingredient(db, "Big", threshold="5000")
    _stock(db, small, 400)  # shortfall 100
    _stock(db, big, 100)  # shortfall 4900

    rows = today_service.low_stock_ingredients(db)
    assert [r["ingredient"].name for r in rows] == ["Big", "Small"]


def test_low_stock_ignores_inactive(db):
    ing = _ingredient(db, "Old", threshold="1000")
    _stock(db, ing, 100)
    inv.delete_ingredient(db, ing.id)
    assert today_service.low_stock_ingredients(db) == []
