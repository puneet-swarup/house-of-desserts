"""Product CRUD routes + recipe editor."""

from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import inventory_service, product_service, recipe_service
from app.utils.sku import validate_sku_format

router = APIRouter()


# ---------------------------------------------------------------
# List
# ---------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def list_products_page(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings
    products = product_service.list_products(db, include_inactive=True)

    capacities = recipe_service.capacity_for_products(db, [p.id for p in products])

    # Per-product unit cost and margin. Small bakery with a handful of
    # SKUs — the per-product loop is fine. If it ever matters, batch it.
    economics: dict[int, dict] = {}
    for p in products:
        cost = recipe_service.recipe_cost(db, p.id)
        price = p.base_price or Decimal("0.00")
        margin = price - cost
        pct = (margin / price * 100).quantize(Decimal("0.01")) if price > 0 else Decimal("0.00")
        economics[p.id] = {
            "unit_cost": cost,
            "unit_price": price,
            "unit_margin": margin,
            "margin_pct": pct,
            "has_recipe": cost > 0,
        }

    return templates.TemplateResponse(
        request=request,
        name="products/list.html",
        context={
            "settings": settings,
            "products": products,
            "capacities": capacities,
            "economics": economics,
        },
    )


# ---------------------------------------------------------------
# Create
# ---------------------------------------------------------------


@router.get("/new", response_class=HTMLResponse)
def new_product_form(request: Request):
    templates = request.app.state.templates
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="products/form.html",
        context={"settings": settings, "product": None},
    )


@router.get("/check-sku")
def check_sku(
    sku: str = "",
    exclude_id: int | None = None,
    db: Session = Depends(get_db),
):
    if not sku.strip():
        return {"available": True, "normalized": "", "reason": None}
    try:
        normalized = validate_sku_format(sku)
    except ValueError:
        return {"available": False, "normalized": "", "reason": "invalid"}
    available = product_service.is_sku_available(db, normalized, exclude_product_id=exclude_id)
    return {
        "available": available,
        "normalized": normalized,
        "reason": None if available else "duplicate",
    }


@router.post("/", response_class=HTMLResponse)
def create_product(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    sku: str = Form(""),
    category: str = Form("Cake"),
    measure_value: str = Form(""),
    measure_unit: str = Form(""),
    pack_size: int = Form(1),
    pack_label: str = Form(""),
    base_price: float = Form(...),
    gst_rate: float = Form(5.0),
    prep_time_hours: int = Form(4),
    description: str = Form(None),
    is_active: str = Form("1"),
):
    templates = request.app.state.templates
    settings = request.app.state.settings

    data = {
        "name": name.strip(),
        "sku": sku.strip(),
        "category": category,
        "measure_value": measure_value.strip() or None,
        "measure_unit": measure_unit.strip() or None,
        "pack_size": pack_size,
        "pack_label": pack_label.strip(),
        "base_price": base_price,
        "gst_rate": gst_rate,
        "prep_time_hours": prep_time_hours,
        "description": description or None,
        "is_active": is_active == "1",
    }

    try:
        product = product_service.create_product(db, data)
    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="products/form.html",
            context={"settings": settings, "product": None, "error": str(e), "form_data": data},
            status_code=400,
        )

    return RedirectResponse(url=f"/products/{product.id}/recipe", status_code=303)


# ---------------------------------------------------------------
# Edit / Delete
# ---------------------------------------------------------------


@router.get("/{product_id}/edit", response_class=HTMLResponse)
def edit_product_form(request: Request, product_id: int, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings
    product = product_service.get_product(db, product_id)
    return templates.TemplateResponse(
        request=request,
        name="products/form.html",
        context={"settings": settings, "product": product},
    )


@router.post("/{product_id}/edit", response_class=HTMLResponse)
def update_product(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db),
    name: str = Form(...),
    sku: str = Form(""),
    category: str = Form("Cake"),
    measure_value: str = Form(""),
    measure_unit: str = Form(""),
    pack_size: int = Form(1),
    pack_label: str = Form(""),
    base_price: float = Form(...),
    gst_rate: float = Form(5.0),
    prep_time_hours: int = Form(4),
    description: str = Form(None),
    is_active: str = Form("1"),
):
    templates = request.app.state.templates
    settings = request.app.state.settings

    data = {
        "name": name.strip(),
        "sku": sku.strip(),
        "category": category,
        "measure_value": measure_value.strip() or None,
        "measure_unit": measure_unit.strip() or None,
        "pack_size": pack_size,
        "pack_label": pack_label.strip(),
        "base_price": base_price,
        "gst_rate": gst_rate,
        "prep_time_hours": prep_time_hours,
        "description": description or None,
        "is_active": is_active == "1",
    }

    try:
        product_service.update_product(db, product_id, data)
    except Exception as e:
        product = product_service.get_product(db, product_id)
        return templates.TemplateResponse(
            request=request,
            name="products/form.html",
            context={"settings": settings, "product": product, "error": str(e), "form_data": data},
            status_code=400,
        )

    return RedirectResponse(url="/products", status_code=303)


@router.post("/{product_id}/delete")
def delete_product_route(product_id: int, db: Session = Depends(get_db)):
    product_service.delete_product(db, product_id)
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------
# Recipe editor
# ---------------------------------------------------------------


@router.get("/{product_id}/recipe", response_class=HTMLResponse)
def recipe_editor(
    request: Request,
    product_id: int,
    saved: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates
    settings = request.app.state.settings

    product = product_service.get_product(db, product_id)
    recipe_lines = recipe_service.list_recipe(db, product_id)
    capacity = recipe_service.capacity_for_product(db, product_id)
    recipe_cost = recipe_service.recipe_cost(db, product_id)
    ingredients = inventory_service.list_ingredients(db, include_inactive=False)

    return templates.TemplateResponse(
        request=request,
        name="products/recipe.html",
        context={
            "settings": settings,
            "product": product,
            "recipe_lines": recipe_lines,
            "capacity": capacity,
            "recipe_cost": recipe_cost,
            "ingredients": ingredients,
            "saved": saved,
            "error": error,
        },
    )


@router.post("/{product_id}/recipe", response_class=HTMLResponse)
async def recipe_save(request: Request, product_id: int, db: Session = Depends(get_db)):
    form = await request.form()
    ing_ids = form.getlist("ingredient_id")
    quantities = form.getlist("quantity")
    unit_rows = form.getlist("unit")

    lines: list[dict] = []
    for idx, (iid_raw, qty_raw) in enumerate(zip(ing_ids, quantities, strict=False)):
        iid = (iid_raw or "").strip()
        qty = (qty_raw or "").strip()
        if not iid or not qty:
            continue
        unit = ""
        if idx < len(unit_rows):
            unit = (unit_rows[idx] or "").strip()
        try:
            lines.append(
                {
                    "ingredient_id": int(iid),
                    "quantity_per_unit": qty,
                    "unit": unit or None,
                }
            )
        except (ValueError, TypeError):
            return RedirectResponse(
                url=f"/products/{product_id}/recipe?error=Invalid+row",
                status_code=303,
            )

    try:
        recipe_service.replace_recipe(db, product_id, lines)
    except Exception as exc:
        from urllib.parse import quote

        return RedirectResponse(
            url=f"/products/{product_id}/recipe?error={quote(str(exc))}",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/products/{product_id}/recipe?saved=1",
        status_code=303,
    )
