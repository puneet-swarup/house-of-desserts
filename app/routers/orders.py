"""
Order routes. HTTP only; business logic in order_service.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer, OrderStatus, Product
from app.services import invoice_service, order_service

router = APIRouter()


def _default_fulfillment() -> str:
    tomorrow_noon = (datetime.now() + timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    return tomorrow_noon.strftime("%Y-%m-%dT%H:%M")


def _product_and_customer_choices(db: Session):
    customers = db.query(Customer).where(Customer.is_active.is_(True)).order_by(Customer.name).all()
    products = db.query(Product).where(Product.is_active.is_(True)).order_by(Product.name).all()
    return customers, products


@router.get("/", response_class=HTMLResponse)
def list_orders_page(request: Request, status: str = "ALL", db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings
    try:
        orders = order_service.list_orders(db, status)
    except Exception:
        db.rollback()
        orders = []
    return templates.TemplateResponse(
        request=request,
        name="orders/list.html",
        context={"settings": settings, "orders": orders, "filter": status},
    )


@router.get("/new", response_class=HTMLResponse)
def new_order_form(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings
    customers, products = _product_and_customer_choices(db)

    return templates.TemplateResponse(
        request=request,
        name="orders/form.html",
        context={
            "settings": settings,
            "customers": customers,
            "products": products,
            "today_date": datetime.now().strftime("%Y-%m-%d"),
            "default_fulfillment": _default_fulfillment(),
            "mode": "create",
            "form_action": "/orders/",
        },
    )


@router.post("/", response_class=HTMLResponse)
def create_order(
    request: Request,
    db: Session = Depends(get_db),
    customer_id: int = Form(...),
    delivery_type: str = Form("PICKUP"),
    fulfillment_date: str = Form(None),
    delivery_address: str = Form(None),
    notes: str = Form(None),
    advance_paid: float = Form(0),
    advance_method: str = Form("UPI"),
    product_id: list[int] = Form(...),
    quantity: list[int] = Form(...),
    order_date: str = Form(None),
):
    templates = request.app.state.templates
    settings = request.app.state.settings

    items = [
        {"product_id": pid, "quantity": qty} for pid, qty in zip(product_id, quantity, strict=True)
    ]

    data = {
        "customer_id": customer_id,
        "order_date": order_date,
        "delivery_type": delivery_type,
        "fulfillment_date": fulfillment_date or None,
        "delivery_address": delivery_address or None,
        "notes": notes or None,
        "items": items,
        "advance_paid": advance_paid,
        "advance_method": advance_method,
    }

    try:
        order = order_service.create_order(db, data)
    except Exception as exc:
        db.rollback()
        customers, products = _product_and_customer_choices(db)
        return templates.TemplateResponse(
            request=request,
            name="orders/form.html",
            context={
                "settings": settings,
                "customers": customers,
                "products": products,
                "today_date": datetime.now().strftime("%Y-%m-%d"),
                "default_fulfillment": _default_fulfillment(),
                "mode": "create",
                "form_action": "/orders/",
                "error": str(exc),
                "form_data": data,
            },
            status_code=400,
        )

    return RedirectResponse(url=f"/orders/{order.id}", status_code=303)


@router.get("/{order_id}/edit", response_class=HTMLResponse)
def edit_order_form(request: Request, order_id: int, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings

    order = order_service.get_order(db, order_id)

    if order.status != OrderStatus.CONFIRMED:
        return RedirectResponse(url=f"/orders/{order_id}", status_code=303)

    customers, products = _product_and_customer_choices(db)
    has_invoice = invoice_service.get_invoice_for_order(db, order_id) is not None

    return templates.TemplateResponse(
        request=request,
        name="orders/form.html",
        context={
            "settings": settings,
            "customers": customers,
            "products": products,
            "today_date": datetime.now().strftime("%Y-%m-%d"),
            "default_fulfillment": _default_fulfillment(),
            "mode": "edit",
            "form_action": f"/orders/{order_id}/edit",
            "order": order,
            "has_invoice": has_invoice,
        },
    )


@router.post("/{order_id}/edit", response_class=HTMLResponse)
def update_order(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    delivery_type: str = Form("PICKUP"),
    fulfillment_date: str = Form(None),
    delivery_address: str = Form(None),
    notes: str = Form(None),
    product_id: list[int] = Form(...),
    quantity: list[int] = Form(...),
):
    templates = request.app.state.templates
    settings = request.app.state.settings

    items = [
        {"product_id": pid, "quantity": qty} for pid, qty in zip(product_id, quantity, strict=True)
    ]

    data = {
        "delivery_type": delivery_type,
        "fulfillment_date": fulfillment_date or None,
        "delivery_address": delivery_address or None,
        "notes": notes or None,
        "items": items,
    }

    try:
        order = order_service.update_order(db, order_id, data)
    except Exception as exc:
        db.rollback()
        # Re-render the edit form with the error
        order = order_service.get_order(db, order_id)
        customers, products = _product_and_customer_choices(db)
        has_invoice = invoice_service.get_invoice_for_order(db, order_id) is not None
        return templates.TemplateResponse(
            request=request,
            name="orders/form.html",
            context={
                "settings": settings,
                "customers": customers,
                "products": products,
                "today_date": datetime.now().strftime("%Y-%m-%d"),
                "default_fulfillment": _default_fulfillment(),
                "mode": "edit",
                "form_action": f"/orders/{order_id}/edit",
                "order": order,
                "has_invoice": has_invoice,
                "error": str(exc),
                "form_data": data,
            },
            status_code=400,
        )

    return RedirectResponse(url=f"/orders/{order.id}", status_code=303)


@router.get("/{order_id}", response_class=HTMLResponse)
def order_detail(request: Request, order_id: int, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings
    order = order_service.get_order(db, order_id)
    return templates.TemplateResponse(
        request=request,
        name="orders/detail.html",
        context={"settings": settings, "order": order},
    )


@router.post("/{order_id}/status")
def update_status(order_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    order = order_service.update_status(db, order_id, status)
    return {"ok": True, "status": order.status.value}


@router.post("/{order_id}/payments")
def add_payment(
    order_id: int,
    db: Session = Depends(get_db),
    amount: float = Form(...),
    method: str = Form("UPI"),
    reference: str = Form(None),
):
    order_service.record_payment(db, order_id, amount, method, reference)
    return RedirectResponse(url=f"/orders/{order_id}", status_code=303)
