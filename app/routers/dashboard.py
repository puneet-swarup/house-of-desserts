"""
Dashboard route — shows today's stats and recent orders.
"""

from datetime import datetime, time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, OrderStatus, Product

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the dashboard page with stats and recent orders."""
    templates = request.app.state.templates
    settings = request.app.state.settings

    # --- Calculate stats ---
    today_start = datetime.combine(datetime.now().date(), time.min)

    # Orders created today
    today_orders = db.execute(
        select(func.count(Order.id)).where(Order.order_date >= today_start)
    ).scalar() or 0

    # Orders pending delivery (READY status, delivery_date is today or future)
    pending_delivery = db.execute(
        select(func.count(Order.id)).where(
            Order.status == OrderStatus.READY
        )
    ).scalar() or 0

    # Total outstanding balance across all non-cancelled orders
    outstanding = db.execute(
        select(func.coalesce(func.sum(Order.balance_due), 0)).where(
            Order.status != OrderStatus.CANCELLED
        )
    ).scalar() or 0

    # Total active products
    total_products = db.execute(
        select(func.count(Product.id)).where(Product.is_active == True)
    ).scalar() or 0

    stats = {
        "today_orders": today_orders,
        "pending_delivery": pending_delivery,
        "outstanding_balance": outstanding,
        "total_products": total_products,
    }

    # Recent orders (last 10)
    recent_orders = db.execute(
        select(Order).order_by(Order.created_at.desc()).limit(10)
    ).scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "settings": settings,
            "stats": stats,
            "recent_orders": recent_orders,
        },
    )   