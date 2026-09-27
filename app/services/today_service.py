"""
Today page business logic — dispatch list, production list, low-stock alerts.

Design note: fulfillment_date is stored as a naive datetime that
represents the customer's local (business timezone) intent — they
typed "15:00" meaning 3pm local. We therefore filter by comparing
the DATE portion of that naive value against the current date in
the business timezone.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import Ingredient, Order, OrderItem, OrderStatus, Product
from app.services import inventory_service


def _today_local() -> date:
    settings = get_settings()
    tz = ZoneInfo(settings.business_timezone)
    return datetime.now(tz).date()


def dispatch_today(db: Session) -> list[Order]:
    today = _today_local()

    orders = (
        db.execute(
            select(Order)
            .options(selectinload(Order.items), selectinload(Order.payments))
            .where(Order.status != OrderStatus.CANCELLED)
            .order_by(Order.fulfillment_date.asc())
        )
        .scalars()
        .all()
    )

    return [o for o in orders if o.fulfillment_date and o.fulfillment_date.date() == today]


def production_this_week(db: Session, days: int = 7) -> dict:
    today = _today_local()
    tomorrow = today + timedelta(days=1)
    horizon = today + timedelta(days=days)

    rows = db.execute(
        select(OrderItem, Order, Product)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(Order.status.in_([OrderStatus.CONFIRMED, OrderStatus.IN_PROGRESS]))
        .order_by(Order.fulfillment_date.asc())
    ).all()

    agg: dict[tuple[str, int], dict] = {}
    order_ids_per_key: dict[tuple[str, int], set[int]] = {}

    for item, order, product in rows:
        if not order.fulfillment_date:
            continue
        fdate = order.fulfillment_date.date()
        if fdate < today or fdate >= horizon:
            continue

        if fdate == today:
            bucket = "urgent"
        elif fdate == tomorrow:
            bucket = "tomorrow"
        else:
            bucket = "later"

        key = (bucket, product.id)
        if key not in agg:
            agg[key] = {
                "sku": product.sku,
                "name": product.name,
                "measure": product.measure_display,
                "pack": product.pack_display,
                "qty": 0,
                "earliest": order.fulfillment_date,
                "prep_hours": product.prep_time_hours,
            }
            order_ids_per_key[key] = set()

        agg[key]["qty"] += item.quantity
        order_ids_per_key[key].add(order.id)
        if order.fulfillment_date < agg[key]["earliest"]:
            agg[key]["earliest"] = order.fulfillment_date

    for key, row in agg.items():
        row["order_count"] = len(order_ids_per_key[key])

    def _sorted(bucket_name: str) -> list[dict]:
        return sorted(
            (v for k, v in agg.items() if k[0] == bucket_name),
            key=lambda r: r["earliest"],
        )

    urgent = _sorted("urgent")
    tomorrow_rows = _sorted("tomorrow")
    later = _sorted("later")

    return {
        "urgent": urgent,
        "tomorrow": tomorrow_rows,
        "later": later,
        "total_units": sum(r["qty"] for r in urgent + tomorrow_rows + later),
    }


def low_stock_ingredients(db: Session) -> list[dict]:
    """
    Active ingredients whose on-hand stock is at or below the reorder
    threshold. Sorted by shortfall descending — the biggest gaps first.
    """
    ings = (
        db.execute(
            select(Ingredient).where(Ingredient.is_active.is_(True)).order_by(Ingredient.name)
        )
        .scalars()
        .all()
    )

    if not ings:
        return []

    stocks = inventory_service.stocks_for(db, [i.id for i in ings])

    out: list[dict] = []
    for ing in ings:
        on_hand = stocks.get(ing.id, Decimal("0"))
        if on_hand <= ing.reorder_threshold:
            out.append(
                {
                    "ingredient": ing,
                    "on_hand": on_hand,
                    "threshold": ing.reorder_threshold,
                    "shortfall": ing.reorder_threshold - on_hand,
                }
            )

    out.sort(key=lambda r: r["shortfall"], reverse=True)
    return out
