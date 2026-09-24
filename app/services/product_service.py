"""Product business logic. Auto-generates SKU when the form leaves it blank."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Product
from app.services.audit_service import log_action
from app.utils.sku import normalize_measure, unique_sku, validate_sku_format


def get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def list_products(db: Session, include_inactive: bool = False) -> list[Product]:
    query = select(Product).order_by(Product.name)
    if not include_inactive:
        query = query.where(Product.is_active.is_(True))
    return list(db.execute(query).scalars().all())


def _prepare_payload(db: Session, data: dict, *, exclude_id: int | None = None) -> dict:
    """Normalize measure, generate/normalize SKU, strip unknown keys."""
    payload = dict(data)

    # Normalize measure
    if "measure_value" in payload or "measure_unit" in payload:
        v, u = normalize_measure(payload.get("measure_value"), payload.get("measure_unit"))
        payload["measure_value"] = v
        payload["measure_unit"] = u

    # SKU: if provided, normalize; else generate
    raw_sku = (payload.get("sku") or "").strip()
    if raw_sku:
        payload["sku"] = validate_sku_format(raw_sku)
    else:
        payload["sku"] = unique_sku(
            db,
            name=payload.get("name") or "",
            measure_value=payload.get("measure_value"),
            measure_unit=payload.get("measure_unit"),
            pack_size=int(payload.get("pack_size") or 1),
            exclude_product_id=exclude_id,
        )
    return payload


def create_product(db: Session, data: dict) -> Product:
    payload = _prepare_payload(db, data)
    product = Product(**payload)
    db.add(product)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"SKU '{payload.get('sku')}' is already in use by an active product",
        ) from exc

    log_action(
        db,
        entity_type="Product",
        entity_id=product.id,
        action="CREATE",
        new_value={
            "sku": product.sku,
            "name": product.name,
            "base_price": product.base_price,
        },
    )
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product_id: int, data: dict) -> Product:
    product = get_product(db, product_id)

    # Only keep keys that are actual product columns
    payload = {k: v for k, v in data.items() if hasattr(product, k)}
    payload = _prepare_payload(db, payload, exclude_id=product.id)

    old = {k: getattr(product, k) for k in payload if hasattr(product, k)}

    for key, value in payload.items():
        setattr(product, key, value)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"SKU '{payload.get('sku')}' is already in use by an active product",
        ) from exc

    log_action(
        db,
        entity_type="Product",
        entity_id=product.id,
        action="UPDATE",
        old_value=old,
        new_value={k: getattr(product, k) for k in payload if hasattr(product, k)},
    )
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product_id: int) -> None:
    product = get_product(db, product_id)
    product.is_active = False
    log_action(
        db,
        entity_type="Product",
        entity_id=product.id,
        action="DELETE",
        old_value={"sku": product.sku, "name": product.name},
    )
    db.commit()


def is_sku_available(
    db: Session, sku: str, *, exclude_product_id: int | None = None
) -> bool:
    """For the live on-the-fly SKU check in the form."""
    try:
        normalized = validate_sku_format(sku)
    except ValueError:
        return False
    q = select(Product).where(Product.sku == normalized)
    if exclude_product_id is not None:
        q = q.where(Product.id != exclude_product_id)
    return db.execute(q).scalar_one_or_none() is None
