"""Tests for product CRUD."""

from app.models import Product


def test_create_product(client, db_session):
    client.post("/products", data={
        "name": "Blueberry Muffin",
        "sku": "BLUE-MUF-01",
        "category": "Pastry",
        "base_price": "150.00",
        "gst_rate": "5.0",
        "prep_time_hours": "2",
        "description": "",
        "is_active": "1",
    })
    product = db_session.query(Product).filter_by(sku="BLUE-MUF-01").first()
    assert product is not None
    assert product.name == "Blueberry Muffin"
    assert product.base_price == 150.0


def test_list_products_shows_created(client, db_session):
    client.post("/products", data={
        "name": "Vegan Cookie", "sku": "VEG-COOK-01", "hsn_code": "1905",
        "category": "Cookie", "base_price": "80.00", "gst_rate": "5.0",
        "prep_time_hours": "1", "description": "", "is_active": "1",
    })
    resp = client.get("/products")
    assert resp.status_code == 200
    assert "Vegan Cookie" in resp.text
    assert "VEG-COOK-01" in resp.text


def test_duplicate_sku_rejected(client, db_session):
    data = {
        "name": "Cake A", "sku": "DUP-001", "hsn_code": "1905",
        "category": "Cake", "base_price": "100.00", "gst_rate": "5.0",
        "prep_time_hours": "2", "description": "", "is_active": "1",
    }
    client.post("/products", data=data)
    assert db_session.query(Product).filter_by(sku="DUP-001").first() is not None

    client.post("/products", data={**data, "name": "Cake B"})
    count = db_session.query(Product).filter_by(sku="DUP-001").count()
    assert count == 1


def test_edit_product(client, db_session):
    client.post("/products", data={
        "name": "Old Name", "sku": "EDIT-001", "hsn_code": "1905",
        "category": "Cake", "base_price": "100.00", "gst_rate": "5.0",
        "prep_time_hours": "2", "description": "", "is_active": "1",
    })
    product = db_session.query(Product).filter_by(sku="EDIT-001").first()

    client.post(f"/products/{product.id}/edit", data={
        "name": "New Name", "sku": "EDIT-001", "hsn_code": "1905",
        "category": "Cake", "base_price": "200.00", "gst_rate": "5.0",
        "prep_time_hours": "3", "description": "Updated", "is_active": "1",
    })
    db_session.refresh(product)
    assert product.name == "New Name"
    assert product.base_price == 200.0


def test_delete_product_soft_delete(client, db_session):
    client.post("/products", data={
        "name": "Delete Me", "sku": "DEL-001", "hsn_code": "1905",
        "category": "Cake", "base_price": "50.00", "gst_rate": "5.0",
        "prep_time_hours": "1", "description": "", "is_active": "1",
    })
    product = db_session.query(Product).filter_by(sku="DEL-001").first()

    resp = client.post(f"/products/{product.id}/delete")
    assert resp.status_code == 200
    db_session.refresh(product)
    assert product.is_active is False


def test_product_form_renders(client):
    resp = client.get("/products/new")
    assert resp.status_code == 200
    assert "Add Product" in resp.text
