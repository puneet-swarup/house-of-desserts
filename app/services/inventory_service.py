"""
Inventory business logic.

Design:
- Ingredient.current_stock is NOT stored. It's computed from StockMovement
  as SUM(delta). Fast at any realistic scale, can never drift.
- Every movement snapshots the ingredient's cost at that moment
  (unit_cost_at_time, total_cost_at_time). Historical COGS is immune
  to later price changes.
- Purchase movements update the ingredient's weighted-average cost.
  Consumption and wastage do not.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Ingredient,
    IngredientKind,
    MovementReason,
    StockMovement,
)
from app.services.audit_service import log_action

# ---------------------------------------------------------------
# Reads
# ---------------------------------------------------------------


def list_ingredients(
    db: Session,
    *,
    kind: str | None = None,
    include_inactive: bool = False,
) -> list[Ingredient]:
    q = select(Ingredient).order_by(Ingredient.name)
    if kind:
        q = q.where(Ingredient.kind == _coerce_kind(kind))
    if not include_inactive:
        q = q.where(Ingredient.is_active.is_(True))
    return list(db.execute(q).scalars().all())


def get_ingredient(db: Session, ingredient_id: int) -> Ingredient:
    ing = db.get(Ingredient, ingredient_id)
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return ing


def on_hand(db: Session, ingredient_id: int) -> Decimal:
    """Physical stock = SUM(delta) across all movements."""
    total = db.execute(
        select(func.coalesce(func.sum(StockMovement.delta), 0)).where(
            StockMovement.ingredient_id == ingredient_id
        )
    ).scalar()
    return Decimal(str(total or 0))


def stocks_for(db: Session, ingredient_ids: list[int]) -> dict[int, Decimal]:
    """Batch on_hand for many ingredients. Avoids N+1 in list views."""
    if not ingredient_ids:
        return {}
    rows = db.execute(
        select(
            StockMovement.ingredient_id,
            func.coalesce(func.sum(StockMovement.delta), 0),
        )
        .where(StockMovement.ingredient_id.in_(ingredient_ids))
        .group_by(StockMovement.ingredient_id)
    ).all()
    return {iid: Decimal(str(total or 0)) for iid, total in rows}


def ledger(
    db: Session,
    ingredient_id: int,
    *,
    limit: int = 100,
) -> list[StockMovement]:
    """Recent movements for one ingredient, newest first."""
    get_ingredient(db, ingredient_id)  # 404 if missing
    return list(
        db.execute(
            select(StockMovement)
            .where(StockMovement.ingredient_id == ingredient_id)
            .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def is_low_stock(ing: Ingredient, on_hand_qty: Decimal) -> bool:
    return on_hand_qty <= ing.reorder_threshold


# ---------------------------------------------------------------
# Writes — CRUD
# ---------------------------------------------------------------


def create_ingredient(db: Session, data: dict) -> Ingredient:
    payload = dict(data)
    if "kind" in payload:
        payload["kind"] = _coerce_kind(payload["kind"])

    ing = Ingredient(**payload)
    db.add(ing)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Ingredient '{data.get('name')}' already exists",
        ) from exc

    log_action(
        db,
        entity_type="Ingredient",
        entity_id=ing.id,
        action="CREATE",
        new_value={"name": ing.name, "unit": ing.unit, "kind": ing.kind.value},
    )
    db.commit()
    db.refresh(ing)
    return ing


def update_ingredient(db: Session, ingredient_id: int, data: dict) -> Ingredient:
    ing = get_ingredient(db, ingredient_id)
    payload = dict(data)
    if "kind" in payload:
        payload["kind"] = _coerce_kind(payload["kind"])

    old = {k: getattr(ing, k) for k in payload if hasattr(ing, k)}
    for k, v in payload.items():
        setattr(ing, k, v)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Ingredient '{data.get('name')}' already exists",
        ) from exc

    log_action(
        db,
        entity_type="Ingredient",
        entity_id=ing.id,
        action="UPDATE",
        old_value=old,
        new_value={k: getattr(ing, k) for k in payload if hasattr(ing, k)},
    )
    db.commit()
    db.refresh(ing)
    return ing


def delete_ingredient(db: Session, ingredient_id: int) -> None:
    ing = get_ingredient(db, ingredient_id)
    ing.is_active = False
    log_action(
        db,
        entity_type="Ingredient",
        entity_id=ing.id,
        action="DELETE",
        old_value={"name": ing.name, "unit": ing.unit},
    )
    db.commit()


# ---------------------------------------------------------------
# Writes — stock movements
# ---------------------------------------------------------------


def record_movement(
    db: Session,
    ingredient_id: int,
    *,
    delta: Decimal | float | str,
    reason: MovementReason | str,
    unit_cost: Decimal | float | str | None = None,
    reference_type: str | None = None,
    reference_id: int | None = None,
    notes: str | None = None,
) -> StockMovement:
    """
    Append a stock movement and (for purchases) update the ingredient's
    weighted-average cost.

    Sign convention:
      PURCHASE, RETURN → delta must be positive
      CONSUMPTION, WASTAGE → delta must be negative
      ADJUSTMENT → either sign accepted
    """
    ing = get_ingredient(db, ingredient_id)

    try:
        delta_d = Decimal(str(delta))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid delta: {delta}") from exc

    if delta_d == 0:
        raise HTTPException(status_code=400, detail="Delta cannot be zero")

    reason_e = _coerce_reason(reason)

    if reason_e in (MovementReason.PURCHASE, MovementReason.RETURN) and delta_d < 0:
        raise HTTPException(status_code=400, detail=f"{reason_e.value} must have a positive delta")
    if reason_e in (MovementReason.CONSUMPTION, MovementReason.WASTAGE) and delta_d > 0:
        raise HTTPException(status_code=400, detail=f"{reason_e.value} must have a negative delta")

    cost = Decimal(str(unit_cost)) if unit_cost is not None else ing.cost_per_unit
    total_cost = cost * delta_d

    # Compute prior stock BEFORE adding this movement
    old_stock = on_hand(db, ingredient_id)

    movement = StockMovement(
        ingredient_id=ingredient_id,
        delta=delta_d,
        reason=reason_e,
        reference_type=reference_type,
        reference_id=reference_id,
        unit_cost_at_time=cost,
        total_cost_at_time=total_cost,
        notes=notes,
    )
    db.add(movement)
    db.flush()

    # Weighted-average cost update on purchases
    if reason_e == MovementReason.PURCHASE and delta_d > 0:
        new_stock = old_stock + delta_d
        if new_stock > 0:
            old_value = old_stock * ing.cost_per_unit
            new_value = delta_d * cost
            ing.cost_per_unit = (old_value + new_value) / new_stock

    log_action(
        db,
        entity_type="StockMovement",
        entity_id=movement.id,
        action=reason_e.value,
        new_value={
            "ingredient_id": ingredient_id,
            "delta": str(delta_d),
            "unit_cost": str(cost),
            "total_cost": str(total_cost),
        },
    )
    db.commit()
    db.refresh(movement)
    return movement


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------


def _coerce_kind(value) -> IngredientKind:
    if isinstance(value, IngredientKind):
        return value
    try:
        return IngredientKind(value)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid kind: {value}") from exc


def _coerce_reason(value) -> MovementReason:
    if isinstance(value, MovementReason):
        return value
    try:
        return MovementReason(value)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid reason: {value}") from exc
