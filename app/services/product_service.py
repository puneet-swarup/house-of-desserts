"""
Product business logic.

Python concept: The "service layer" sits between the HTTP router and the
database. Routers handle HTTP concerns (parse request, return response).
Services handle business rules (validate SKU uniqueness, calculate totals).
This separation means if you later add a CLI or API, the logic is reusable.
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.audit_service import log_action

from app.models import Product


def get_product(db: Session, product_id: int) -> Product:
    """Fetch a product by ID or raise 404."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def list_products(db: Session, include_inactive: bool = False) -> list[Product]:
    """List all products, optionally including inactive ones."""
    query = select(Product).order_by(Product.name)
    if not include_inactive:
        query = query.where(Product.is_active == True)
    return list(db.execute(query).scalars().all())


def create_product(db: Session, data: dict) -> Product:
    """Create a new product. Validates SKU uniqueness."""
    # Check SKU doesn't already exist
    existing = db.execute(
        select(Product).where(Product.sku == data["sku"])
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"SKU '{data['sku']}' already exists")

    product = Product(**data)
    db.add(product)
    db.commit()
    db.refresh(product)
    log_action(
        db, entity_type="Product", entity_id=product.id, action="CREATE",
        new_value={"sku": data["sku"], "name": data["name"], "price": data["base_price"]},
    )
    return product


def update_product(db: Session, product_id: int, data: dict) -> Product:
    """Update an existing product. Only updates fields that are provided."""
    product = get_product(db, product_id)

    # Check SKU uniqueness if SKU is being changed
    if "sku" in data and data["sku"] != product.sku:
        existing = db.execute(
            select(Product).where(Product.sku == data["sku"])
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail=f"SKU '{data['sku']}' already exists")

    for key, value in data.items():
        if value is not None:
            setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product_id: int) -> None:
    """Soft-delete: mark as inactive instead of removing."""
    product = get_product(db, product_id)
    product.is_active = False
    db.commit()
    log_action(
        db, entity_type="Product", entity_id=product.id, action="DELETE",
        old_value={"sku": product.sku, "name": product.name},
    )