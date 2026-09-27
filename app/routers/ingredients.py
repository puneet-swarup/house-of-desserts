"""
Ingredients router — CRUD plus stock movement recording.

Note on cost:
- Cost per unit is a DERIVED value on the Ingredient model. It updates
  automatically on every Purchase movement (weighted average).
- The create/edit forms therefore do NOT expose it as an editable field.
- The only place cost is entered is:
    1. The "Opening stock" section on the create form (if quantity provided)
    2. The "Record a movement" form on the detail page, for purchases
"""

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import inventory_service

router = APIRouter()


def _parse_decimal_or_none(raw: str | None) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


# ---------------------------------------------------------------
# List
# ---------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
def list_page(
    request: Request,
    kind: str = "",
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates
    settings = request.app.state.settings

    ingredients = inventory_service.list_ingredients(
        db,
        kind=kind or None,
        include_inactive=True,
    )
    stocks = inventory_service.stocks_for(db, [i.id for i in ingredients])

    rows = []
    for ing in ingredients:
        on_hand = stocks.get(ing.id, Decimal("0"))
        rows.append(
            {
                "ingredient": ing,
                "on_hand": on_hand,
                "low": ing.is_active and inventory_service.is_low_stock(ing, on_hand),
            }
        )

    low_count = sum(1 for r in rows if r["low"])

    return templates.TemplateResponse(
        request=request,
        name="ingredients/list.html",
        context={
            "settings": settings,
            "rows": rows,
            "filter_kind": kind,
            "low_count": low_count,
        },
    )


# ---------------------------------------------------------------
# Create
# ---------------------------------------------------------------


@router.get("/new", response_class=HTMLResponse)
def new_form(request: Request):
    templates = request.app.state.templates
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="ingredients/form.html",
        context={"settings": settings, "ingredient": None},
    )


@router.post("", response_class=HTMLResponse)
async def create(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings

    form = await request.form()

    # Ingredient identity + policy. No cost here — it's derived from purchases.
    data = {
        "name": (form.get("name") or "").strip(),
        "kind": form.get("kind") or "RAW",
        "unit": (form.get("unit") or "").strip(),
        "reorder_threshold": _parse_decimal_or_none(form.get("reorder_threshold")) or Decimal("0"),
        "notes": (form.get("notes") or "").strip() or None,
        "is_active": form.get("is_active") == "1",
    }

    # Opening stock — both values kept as raw strings for form re-render.
    opening_qty_raw = (form.get("initial_stock") or "").strip()
    opening_cost_raw = (form.get("initial_stock_cost") or "").strip()

    form_data = {
        **data,
        "initial_stock": opening_qty_raw,
        "initial_stock_cost": opening_cost_raw,
    }

    if not data["name"]:
        return templates.TemplateResponse(
            request=request,
            name="ingredients/form.html",
            context={
                "settings": settings,
                "ingredient": None,
                "error": "Name is required",
                "form_data": form_data,
            },
            status_code=400,
        )

    try:
        ing = inventory_service.create_ingredient(db, data)
    except Exception as exc:
        return templates.TemplateResponse(
            request=request,
            name="ingredients/form.html",
            context={
                "settings": settings,
                "ingredient": None,
                "error": str(exc),
                "form_data": form_data,
            },
            status_code=400,
        )

    # If an opening quantity was provided, record it as a PURCHASE movement.
    # This gives the ingredient its starting stock and its first cost basis.
    if opening_qty_raw:
        qty = _parse_decimal_or_none(opening_qty_raw)
        cost = _parse_decimal_or_none(opening_cost_raw)
        if qty is not None and qty > 0:
            try:
                inventory_service.record_movement(
                    db,
                    ing.id,
                    delta=qty,
                    reason="PURCHASE",
                    unit_cost=cost,  # None → falls back to ingredient's current cost (0)
                    notes="Opening stock",
                )
            except Exception:
                # Ingredient was created successfully. A failed opening
                # movement is non-fatal — user can record it on the detail page.
                pass

    return RedirectResponse(url=f"/ingredients/{ing.id}", status_code=303)


# ---------------------------------------------------------------
# Detail / Ledger
# ---------------------------------------------------------------


@router.get("/{ingredient_id}", response_class=HTMLResponse)
def detail(
    request: Request,
    ingredient_id: int,
    moved: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates
    settings = request.app.state.settings

    ing = inventory_service.get_ingredient(db, ingredient_id)
    on_hand = inventory_service.on_hand(db, ingredient_id)
    movements = inventory_service.ledger(db, ingredient_id, limit=200)

    return templates.TemplateResponse(
        request=request,
        name="ingredients/detail.html",
        context={
            "settings": settings,
            "ingredient": ing,
            "on_hand": on_hand,
            "low": ing.is_active and inventory_service.is_low_stock(ing, on_hand),
            "movements": movements,
            "moved": moved,
            "error": error,
            "reasons": ["PURCHASE", "WASTAGE", "RETURN", "ADJUSTMENT"],
        },
    )


# ---------------------------------------------------------------
# Edit / Delete
# ---------------------------------------------------------------


@router.get("/{ingredient_id}/edit", response_class=HTMLResponse)
def edit_form(request: Request, ingredient_id: int, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings
    ing = inventory_service.get_ingredient(db, ingredient_id)
    return templates.TemplateResponse(
        request=request,
        name="ingredients/form.html",
        context={"settings": settings, "ingredient": ing},
    )


@router.post("/{ingredient_id}/edit", response_class=HTMLResponse)
async def update(request: Request, ingredient_id: int, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings

    form = await request.form()

    # Same shape as create — no cost. Cost changes only through movements.
    data = {
        "name": (form.get("name") or "").strip(),
        "kind": form.get("kind") or "RAW",
        "unit": (form.get("unit") or "").strip(),
        "reorder_threshold": _parse_decimal_or_none(form.get("reorder_threshold")) or Decimal("0"),
        "notes": (form.get("notes") or "").strip() or None,
        "is_active": form.get("is_active") == "1",
    }

    try:
        inventory_service.update_ingredient(db, ingredient_id, data)
    except Exception as exc:
        ing = inventory_service.get_ingredient(db, ingredient_id)
        return templates.TemplateResponse(
            request=request,
            name="ingredients/form.html",
            context={"settings": settings, "ingredient": ing, "error": str(exc), "form_data": data},
            status_code=400,
        )

    return RedirectResponse(url=f"/ingredients/{ingredient_id}", status_code=303)


@router.post("/{ingredient_id}/delete")
def soft_delete(ingredient_id: int, db: Session = Depends(get_db)):
    inventory_service.delete_ingredient(db, ingredient_id)
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------
# Record a stock movement
# ---------------------------------------------------------------


@router.post("/{ingredient_id}/move", response_class=HTMLResponse)
async def move(request: Request, ingredient_id: int, db: Session = Depends(get_db)):
    form = await request.form()

    reason = (form.get("reason") or "").strip().upper()
    direction = (form.get("direction") or "+").strip()
    quantity_raw = form.get("quantity") or ""
    unit_cost_raw = form.get("unit_cost") or None
    notes = (form.get("notes") or "").strip() or None

    try:
        qty = Decimal(str(quantity_raw))
    except (InvalidOperation, ValueError):
        return RedirectResponse(
            url=f"/ingredients/{ingredient_id}?error=Invalid quantity",
            status_code=303,
        )

    if qty <= 0:
        return RedirectResponse(
            url=f"/ingredients/{ingredient_id}?error=Quantity must be positive",
            status_code=303,
        )

    if reason in ("PURCHASE", "RETURN"):
        delta = qty
    elif reason in ("WASTAGE", "CONSUMPTION"):
        delta = -qty
    elif reason == "ADJUSTMENT":
        delta = qty if direction == "+" else -qty
    else:
        return RedirectResponse(
            url=f"/ingredients/{ingredient_id}?error=Invalid reason",
            status_code=303,
        )

    try:
        inventory_service.record_movement(
            db,
            ingredient_id,
            delta=delta,
            reason=reason,
            unit_cost=_parse_decimal_or_none(unit_cost_raw),
            notes=notes,
        )
    except Exception as exc:
        return RedirectResponse(
            url=f"/ingredients/{ingredient_id}?error={exc}",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/ingredients/{ingredient_id}?moved=1",
        status_code=303,
    )
