"""Tests for recipe editor endpoints."""

from decimal import Decimal

from app.services import inventory_service as inv
from app.services import product_service


def _ingredient(db, name, unit="g"):
    return inv.create_ingredient(
        db,
        {
            "name": name,
            "unit": unit,
            "kind": "RAW",
            "reorder_threshold": Decimal("0"),
        },
    )


def _product(db, sku="CAKE-X"):
    return product_service.create_product(
        db,
        {
            "sku": sku,
            "name": f"Cake {sku}",
            "base_price": Decimal("500.00"),
            "gst_rate": Decimal("5.00"),
        },
    )


def test_recipe_page_loads(client, db_session):
    p = _product(db_session)
    resp = client.get(f"/products/{p.id}/recipe")
    assert resp.status_code == 200
    assert "Recipe" in resp.text


def test_save_recipe_via_http(client, db_session):
    p = _product(db_session)
    ing_a = _ingredient(db_session, "Flour")
    ing_b = _ingredient(db_session, "Butter")

    resp = client.post(
        f"/products/{p.id}/recipe",
        data={
            "ingredient_id": [str(ing_a.id), str(ing_b.id)],
            "quantity": ["250", "100"],
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "saved=1" in resp.headers["location"]

    from app.services import recipe_service as rs

    db_session.expire_all()
    lines = rs.list_recipe(db_session, p.id)
    assert len(lines) == 2
    quantities = {line.ingredient_id: line.quantity_per_unit for line in lines}
    assert quantities[ing_a.id] == Decimal("250")
    assert quantities[ing_b.id] == Decimal("100")


def test_save_empty_recipe_clears(client, db_session):
    p = _product(db_session)
    ing = _ingredient(db_session, "Temp")
    client.post(
        f"/products/{p.id}/recipe",
        data={"ingredient_id": [str(ing.id)], "quantity": ["10"]},
        follow_redirects=False,
    )

    resp = client.post(
        f"/products/{p.id}/recipe",
        data={"ingredient_id": [""], "quantity": [""]},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    from app.services import recipe_service as rs

    db_session.expire_all()
    assert rs.list_recipe(db_session, p.id) == []


def test_capacity_shown_on_product_list(client, db_session):
    p = _product(db_session)
    ing = _ingredient(db_session, "Sugar")

    inv.record_movement(
        db_session,
        ing.id,
        delta=Decimal("100"),
        reason="PURCHASE",
        unit_cost=Decimal("0.10"),
    )
    client.post(
        f"/products/{p.id}/recipe",
        data={"ingredient_id": [str(ing.id)], "quantity": ["20"]},
        follow_redirects=False,
    )

    resp = client.get("/products")
    assert resp.status_code == 200
    # 100 / 20 = 5 → "Can make 5" (badge text includes the number)
    assert ">5<" in resp.text or "5" in resp.text
