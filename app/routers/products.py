"""Product CRUD routes."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import product_service
from app.utils.sku import validate_sku_format

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def list_products_page(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings
    products = product_service.list_products(db, include_inactive=True)
    return templates.TemplateResponse(
        request=request,
        name="products/list.html",
        context={"settings": settings, "products": products},
    )


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
    """
    Live SKU uniqueness check for the product form.
    Returns {available: bool, normalized: str, reason: str|None}
    """
    if not sku.strip():
        return {"available": True, "normalized": "", "reason": None}
    try:
        normalized = validate_sku_format(sku)
    except ValueError:
        return {"available": False, "normalized": "", "reason": "invalid"}
    available = product_service.is_sku_available(
        db, normalized, exclude_product_id=exclude_id
    )
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
        product_service.create_product(db, data)
    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="products/form.html",
            context={
                "settings": settings,
                "product": None,
                "error": str(e),
                "form_data": data,
            },
            status_code=400,
        )
    return RedirectResponse(url="/products", status_code=303)


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
            context={
                "settings": settings,
                "product": product,
                "error": str(e),
                "form_data": data,
            },
            status_code=400,
        )
    return RedirectResponse(url="/products", status_code=303)


@router.post("/{product_id}/delete")
def delete_product_route(product_id: int, db: Session = Depends(get_db)):
    product_service.delete_product(db, product_id)
    return JSONResponse({"ok": True})
