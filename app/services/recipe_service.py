"""
Recipe (Bill of Materials) business logic.

A recipe is the list of ingredients consumed per unit of a product.
Each line pairs one Product with one Ingredient and a quantity.

Two derived values are computed here, never stored:
  - recipe_cost(product)   — ingredient cost to make one unit
  - capacity(product)      — how many more units the current stock allows,
                             and which ingredient is the bottleneck

Unit rule: a recipe line's quantity is expressed in the ingredient's own
unit ("250 g flour" if the ingredient is measured in g). We don't do
automatic unit conversion in v1. Validate and reject mismatched units.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Ingredient, Product, ProductIngredient
from app.services import inventory_service
from app.services.audit_service import log_action

# ---------------------------------------------------------------
# Reads
# ---------------------------------------------------------------


def list_recipe(db: Session, product_id: int) -> list[ProductIngredient]:
    """Recipe lines for one product, stable order."""
    return list(
        db.execute(
            select(ProductIngredient)
            .where(ProductIngredient.product_id == product_id)
            .order_by(ProductIngredient.id)
        )
        .scalars()
        .all()
    )


def recipe_cost(db: Session, product_id: int) -> Decimal:
    """
    Total ingredient cost to make one unit of this product.

    Uses each ingredient's CURRENT weighted-average cost. This is not
    a snapshot — it reflects today's prices. For per-order COGS history,
    see StockMovement.total_cost_at_time captured at consumption.
    """
    lines = list_recipe(db, product_id)
    total = Decimal("0.0000")
    for line in lines:
        unit_cost = line.ingredient.cost_per_unit or Decimal("0")
        total += line.quantity_per_unit * unit_cost
    return total.quantize(Decimal("0.01"))


def capacity_for_product(db: Session, product_id: int) -> dict:
    """
    How many more units of this product can be made from current stock.

    Returns:
        {
          "has_recipe": bool,
          "capacity": int | None,        # None if no recipe lines
          "bottleneck": Ingredient | None,
          "lines": [
              {"ingredient": Ingredient,
               "available": Decimal,
               "per_unit": Decimal,
               "possible": int},
              ...
          ]
        }
    """
    lines = list_recipe(db, product_id)
    if not lines:
        return {
            "has_recipe": False,
            "capacity": None,
            "bottleneck": None,
            "lines": [],
        }

    stocks = inventory_service.stocks_for(db, [line.ingredient_id for line in lines])

    min_possible: int | None = None
    bottleneck: Ingredient | None = None
    detail = []

    for line in lines:
        available = stocks.get(line.ingredient_id, Decimal("0"))
        per_unit = line.quantity_per_unit

        possible = 0 if per_unit <= 0 else int(available / per_unit)

        detail.append(
            {
                "ingredient": line.ingredient,
                "available": available,
                "per_unit": per_unit,
                "possible": possible,
            }
        )

        if min_possible is None or possible < min_possible:
            min_possible = possible
            bottleneck = line.ingredient

    return {
        "has_recipe": True,
        "capacity": min_possible,
        "bottleneck": bottleneck,
        "lines": detail,
    }


def capacity_for_products(db: Session, product_ids: list[int]) -> dict[int, dict]:
    """Batch version of capacity_for_product. Avoids N+1 in list views."""
    if not product_ids:
        return {}

    # Fetch all recipe lines for these products in one query
    rows = (
        db.execute(
            select(ProductIngredient)
            .where(ProductIngredient.product_id.in_(product_ids))
            .order_by(ProductIngredient.id)
        )
        .scalars()
        .all()
    )

    # Group by product
    by_product: dict[int, list[ProductIngredient]] = {}
    for row in rows:
        by_product.setdefault(row.product_id, []).append(row)

    # Batch on_hand for every ingredient we touch
    all_ing_ids = list({r.ingredient_id for r in rows})
    stocks = inventory_service.stocks_for(db, all_ing_ids)

    result: dict[int, dict] = {}
    for pid in product_ids:
        lines = by_product.get(pid, [])
        if not lines:
            result[pid] = {
                "has_recipe": False,
                "capacity": None,
                "bottleneck": None,
                "lines": [],
            }
            continue

        min_possible: int | None = None
        bottleneck: Ingredient | None = None
        detail = []
        for line in lines:
            available = stocks.get(line.ingredient_id, Decimal("0"))
            per_unit = line.quantity_per_unit
            possible = int(available / per_unit) if per_unit > 0 else 0
            detail.append(
                {
                    "ingredient": line.ingredient,
                    "available": available,
                    "per_unit": per_unit,
                    "possible": possible,
                }
            )
            if min_possible is None or possible < min_possible:
                min_possible = possible
                bottleneck = line.ingredient

        result[pid] = {
            "has_recipe": True,
            "capacity": min_possible,
            "bottleneck": bottleneck,
            "lines": detail,
        }
    return result


# ---------------------------------------------------------------
# Writes
# ---------------------------------------------------------------


def upsert_recipe_line(
    db: Session,
    product_id: int,
    ingredient_id: int,
    quantity_per_unit: Decimal | str | float,
    notes: str | None = None,
) -> ProductIngredient:
    """
    Add a recipe line, or update the quantity if the pair already exists.

    Rejects:
      - Non-existent product or ingredient
      - quantity_per_unit <= 0
      - Inactive ingredient
    """
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    ing = db.get(Ingredient, ingredient_id)
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if not ing.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Ingredient '{ing.name}' is inactive",
        )

    try:
        qty = Decimal(str(quantity_per_unit))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid quantity") from exc

    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    existing = db.execute(
        select(ProductIngredient).where(
            ProductIngredient.product_id == product_id,
            ProductIngredient.ingredient_id == ingredient_id,
        )
    ).scalar_one_or_none()

    if existing:
        old_qty = existing.quantity_per_unit
        existing.quantity_per_unit = qty
        existing.notes = notes
        log_action(
            db,
            entity_type="RecipeLine",
            entity_id=existing.id,
            action="UPDATE",
            old_value={"quantity_per_unit": str(old_qty)},
            new_value={"quantity_per_unit": str(qty)},
        )
    else:
        existing = ProductIngredient(
            product_id=product_id,
            ingredient_id=ingredient_id,
            quantity_per_unit=qty,
            notes=notes,
        )
        db.add(existing)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="This ingredient is already part of the recipe",
            ) from exc
        log_action(
            db,
            entity_type="RecipeLine",
            entity_id=existing.id,
            action="CREATE",
            new_value={
                "product_id": product_id,
                "ingredient_id": ingredient_id,
                "quantity_per_unit": str(qty),
            },
        )

    db.commit()
    db.refresh(existing)
    return existing


def remove_recipe_line(db: Session, line_id: int) -> None:
    line = db.get(ProductIngredient, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Recipe line not found")

    log_action(
        db,
        entity_type="RecipeLine",
        entity_id=line.id,
        action="DELETE",
        old_value={
            "product_id": line.product_id,
            "ingredient_id": line.ingredient_id,
            "quantity_per_unit": str(line.quantity_per_unit),
        },
    )
    db.delete(line)
    db.commit()


def replace_recipe(
    db: Session,
    product_id: int,
    lines: list[dict],
) -> list[ProductIngredient]:
    """
    Replace all recipe lines for a product in one transaction.

    Each entry in `lines`:
        {"ingredient_id": int, "quantity_per_unit": Decimal|str|float, "notes": str|None}

    Lines with duplicate ingredient_id are rejected. Empty list clears the recipe.
    """
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Validate for duplicates and non-positive quantities before mutating anything
    seen: set[int] = set()
    normalized: list[dict] = []
    for raw in lines:
        iid = int(raw["ingredient_id"])
        if iid in seen:
            raise HTTPException(
                status_code=400,
                detail=f"Ingredient {iid} listed twice in the recipe",
            )
        seen.add(iid)

        ing = db.get(Ingredient, iid)
        if not ing or not ing.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"Ingredient {iid} not found or inactive",
            )

        try:
            qty = Decimal(str(raw["quantity_per_unit"]))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid quantity") from exc
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be positive")

        normalized.append(
            {
                "ingredient_id": iid,
                "quantity_per_unit": qty,
                "notes": (raw.get("notes") or None),
            }
        )

    # Delete existing, insert new
    existing = list_recipe(db, product_id)
    for line in existing:
        db.delete(line)
    db.flush()

    created: list[ProductIngredient] = []
    for row in normalized:
        new_line = ProductIngredient(
            product_id=product_id,
            ingredient_id=row["ingredient_id"],
            quantity_per_unit=row["quantity_per_unit"],
            notes=row["notes"],
        )
        db.add(new_line)
        created.append(new_line)
    db.flush()

    log_action(
        db,
        entity_type="Product",
        entity_id=product_id,
        action="RECIPE_REPLACED",
        new_value={"line_count": len(created)},
    )
    db.commit()
    for line in created:
        db.refresh(line)
    return created
