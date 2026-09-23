"""
Product CRUD routes — list, create, edit, delete.

Python concept: A "router" is a group of related HTTP endpoints.
Each function here is a "route handler" — it receives an HTTP request,
does work (via services), and returns an HTML page or redirect.
"""

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import product_service
from app.schemas.product import ProductCreate

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def list_products_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Show all products in a card grid."""
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
    """Show the empty product creation form."""
    templates = request.app.state.templates
    settings = request.app.state.settings

    return templates.TemplateResponse(
        request=request,
        name="products/form.html",
        context={"settings": settings, "product": None},
    )


@router.post("/", response_class=HTMLResponse)
def create_product(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    sku: str = Form(...),
    hsn_code: str = Form("1905"),
    category: str = Form("Cake"),
    base_price: float = Form(...),
    gst_rate: float = Form(5.0),
    prep_time_hours: int = Form(4),
    description: str = Form(None),
    is_active: str = Form("1"),  # Checkboxes send "1" or are absent
):
    """Handle product creation form submission."""
    templates = request.app.state.templates
    settings = request.app.state.settings

    data = {
        "name": name,
        "sku": sku,
        "hsn_code": hsn_code,
        "category": category,
        "base_price": base_price,
        "gst_rate": gst_rate,
        "prep_time_hours": prep_time_hours,
        "description": description or None,
        "is_active": is_active == "1",
    }

    try:
        product_service.create_product(db, data)
    except Exception as e:
        # Re-render form with error
        return templates.TemplateResponse(
            request=request,
            name="products/form.html",
            context={
                "settings": settings,
                "product": None,
                "error": str(e),
            },
            status_code=400,
        )

    # Redirect to product list (Post/Redirect/Get pattern)
    return RedirectResponse(url="/products", status_code=303)


@router.get("/{product_id}/edit", response_class=HTMLResponse)
def edit_product_form(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db),
):
    """Show the product edit form pre-filled with current values."""
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
    sku: str = Form(...),
    hsn_code: str = Form("1905"),
    category: str = Form("Cake"),
    base_price: float = Form(...),
    gst_rate: float = Form(5.0),
    prep_time_hours: int = Form(4),
    description: str = Form(None),
    is_active: str = Form("1"),
):
    """Handle product update form submission."""
    templates = request.app.state.templates
    settings = request.app.state.settings

    data = {
        "name": name,
        "sku": sku,
        "hsn_code": hsn_code,
        "category": category,
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
            context={"settings": settings, "product": product, "error": str(e)},
            status_code=400,
        )

    return RedirectResponse(url="/products", status_code=303)


@router.post("/{product_id}/delete")
def delete_product_route(
    product_id: int,
    db: Session = Depends(get_db),
):
    """Soft-delete a product (mark inactive). Called via HTMX."""
    product_service.delete_product(db, product_id)
    return {"ok": True}   