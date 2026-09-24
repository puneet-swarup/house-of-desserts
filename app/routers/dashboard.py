"""
Dashboard route — today's stats and recent orders.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, OrderStatus, Product
from app.utils.time import business_today_bounds_utc

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings

    today_start, today_end = business_today_bounds_utc()

    today_orders = (
        db.execute(
            select(func.count(Order.id)).where(
                Order.order_date >= today_start,
                Order.order_date <= today_end,
            )
        ).scalar()
        or 0
    )

    fulfillments_today = (
        db.execute(
            select(func.count(Order.id)).where(
                Order.fulfillment_date >= today_start,
                Order.fulfillment_date <= today_end,
                Order.status.not_in([OrderStatus.PAID, OrderStatus.CANCELLED]),
            )
        ).scalar()
        or 0
    )

    ready_count = (
        db.execute(
            select(func.count(Order.id)).where(Order.status == OrderStatus.READY)
        ).scalar()
        or 0
    )

    outstanding = (
        db.execute(
            select(func.coalesce(func.sum(Order.balance_due), 0)).where(
                Order.status != OrderStatus.CANCELLED
            )
        ).scalar()
        or 0
    )

    total_products = (
        db.execute(
            select(func.count(Product.id)).where(Product.is_active.is_(True))
        ).scalar()
        or 0
    )

    stats = {
        "today_orders": today_orders,
        "fulfillments_today": fulfillments_today,
        "ready_count": ready_count,
        "outstanding_balance": outstanding,
        "total_products": total_products,
    }

    recent_orders = (
        db.execute(select(Order).order_by(Order.created_at.desc()).limit(10))
        .scalars()
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "settings": settings,
            "stats": stats,
            "recent_orders": recent_orders,
            "now": datetime.now(),
        },
    )
