"""Tests for ingredients HTTP endpoints."""

from decimal import Decimal

from app.models import MovementReason, StockMovement
from app.services import inventory_service as inv


def _create_via_http(client, **overrides):
    """Create an ingredient with sensible defaults. No cost_per_unit — it's derived."""
    payload = {
        "name": "All-purpose flour",
        "kind": "RAW",
        "unit": "g",
        "reorder_threshold": "1000",
        "notes": "",
        "is_active": "1",
    }
    payload.update(overrides)
    return client.post("/ingredients", data=payload, follow_redirects=False)


def test_list_page_loads(client):
    resp = client.get("/ingredients")
    assert resp.status_code == 200
    assert "Inventory" in resp.text


def test_create_ingredient_via_http(client, db_session):
    resp = _create_via_http(client)
    assert resp.status_code == 303
    assert "/ingredients/" in resp.headers["location"]

    from app.models import Ingredient

    ing = db_session.query(Ingredient).first()
    assert ing is not None
    assert ing.name == "All-purpose flour"
    # No cost provided → defaults to zero
    assert ing.cost_per_unit == Decimal("0")


def test_create_with_opening_stock(client, db_session):
    """Opening stock is recorded as a PURCHASE movement and sets the cost."""
    resp = client.post(
        "/ingredients",
        data={
            "name": "Cocoa powder",
            "kind": "RAW",
            "unit": "g",
            "reorder_threshold": "500",
            "initial_stock": "2000",
            "initial_stock_cost": "0.80",
            "notes": "",
            "is_active": "1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    from app.models import Ingredient

    db_session.expire_all()
    ing = db_session.query(Ingredient).filter_by(name="Cocoa powder").first()
    assert ing is not None

    # Stock is on hand
    assert inv.on_hand(db_session, ing.id) == Decimal("2000")

    # Cost was set from the opening purchase
    assert ing.cost_per_unit == Decimal("0.80")

    # Ledger has exactly one PURCHASE, with the snapshot cost
    movements = db_session.query(StockMovement).filter_by(ingredient_id=ing.id).all()
    assert len(movements) == 1
    m = movements[0]
    assert m.reason == MovementReason.PURCHASE
    assert m.delta == Decimal("2000")
    assert m.unit_cost_at_time == Decimal("0.80")
    assert m.total_cost_at_time == Decimal("1600")


def test_create_without_opening_stock_starts_at_zero(client, db_session):
    _create_via_http(client, name="Zero start")
    from app.models import Ingredient

    ing = db_session.query(Ingredient).filter_by(name="Zero start").first()
    assert inv.on_hand(db_session, ing.id) == Decimal("0")
    # No movements
    assert db_session.query(StockMovement).filter_by(ingredient_id=ing.id).count() == 0


def test_create_with_opening_qty_no_cost(client, db_session):
    """Opening qty without cost → ingredient cost stays zero, stock is on hand."""
    resp = client.post(
        "/ingredients",
        data={
            "name": "Old stock",
            "kind": "RAW",
            "unit": "g",
            "reorder_threshold": "0",
            "initial_stock": "500",
            "initial_stock_cost": "",
            "notes": "",
            "is_active": "1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    from app.models import Ingredient

    db_session.expire_all()
    ing = db_session.query(Ingredient).filter_by(name="Old stock").first()
    assert inv.on_hand(db_session, ing.id) == Decimal("500")
    assert ing.cost_per_unit == Decimal("0")


def test_detail_page_loads(client, db_session):
    _create_via_http(client, name="Sugar")
    from app.models import Ingredient

    ing = db_session.query(Ingredient).filter_by(name="Sugar").first()

    resp = client.get(f"/ingredients/{ing.id}")
    assert resp.status_code == 200
    assert "Sugar" in resp.text
    assert "Ledger" in resp.text


def test_purchase_via_http_increases_stock(client, db_session):
    _create_via_http(client, name="Butter")
    from app.models import Ingredient

    ing = db_session.query(Ingredient).filter_by(name="Butter").first()

    resp = client.post(
        f"/ingredients/{ing.id}/move",
        data={"reason": "PURCHASE", "quantity": "500", "unit_cost": "0.10", "notes": "First buy"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    db_session.expire_all()
    assert inv.on_hand(db_session, ing.id) == Decimal("500")

    ing = db_session.get(Ingredient, ing.id)
    assert ing.cost_per_unit == Decimal("0.10")


def test_wastage_via_http_has_negative_delta(client, db_session):
    _create_via_http(client, name="Eggs")
    from app.models import Ingredient

    ing = db_session.query(Ingredient).filter_by(name="Eggs").first()

    inv.record_movement(
        db_session,
        ing.id,
        delta=Decimal("30"),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal("5"),
    )

    resp = client.post(
        f"/ingredients/{ing.id}/move",
        data={"reason": "WASTAGE", "quantity": "2"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    db_session.expire_all()
    movements = (
        db_session.query(StockMovement)
        .filter_by(ingredient_id=ing.id, reason=MovementReason.WASTAGE)
        .all()
    )
    assert len(movements) == 1
    assert movements[0].delta == Decimal("-2")
    assert inv.on_hand(db_session, ing.id) == Decimal("28")


def test_adjustment_direction_minus(client, db_session):
    _create_via_http(client, name="Chocolate")
    from app.models import Ingredient

    ing = db_session.query(Ingredient).filter_by(name="Chocolate").first()

    inv.record_movement(
        db_session,
        ing.id,
        delta=Decimal("100"),
        reason=MovementReason.PURCHASE,
        unit_cost=Decimal("0.5"),
    )

    resp = client.post(
        f"/ingredients/{ing.id}/move",
        data={"reason": "ADJUSTMENT", "quantity": "10", "direction": "-"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    db_session.expire_all()
    assert inv.on_hand(db_session, ing.id) == Decimal("90")


def test_zero_quantity_rejected(client, db_session):
    _create_via_http(client, name="Vanilla")
    from app.models import Ingredient

    ing = db_session.query(Ingredient).filter_by(name="Vanilla").first()

    resp = client.post(
        f"/ingredients/{ing.id}/move",
        data={"reason": "PURCHASE", "quantity": "0"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=" in resp.headers["location"]


def test_edit_ingredient(client, db_session):
    _create_via_http(client, name="Old Name")
    from app.models import Ingredient

    ing = db_session.query(Ingredient).filter_by(name="Old Name").first()

    # Note: no cost_per_unit in the payload — the edit form doesn't send it.
    resp = client.post(
        f"/ingredients/{ing.id}/edit",
        data={
            "name": "New Name",
            "kind": "PACKAGING",
            "unit": "pcs",
            "reorder_threshold": "20",
            "notes": "",
            "is_active": "1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    db_session.expire_all()
    ing = db_session.get(Ingredient, ing.id)
    assert ing.name == "New Name"
    assert ing.unit == "pcs"


def test_soft_delete_endpoint(client, db_session):
    _create_via_http(client, name="Delete Me")
    from app.models import Ingredient

    ing = db_session.query(Ingredient).filter_by(name="Delete Me").first()

    resp = client.post(f"/ingredients/{ing.id}/delete")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    db_session.expire_all()
    ing = db_session.get(Ingredient, ing.id)
    assert ing.is_active is False
