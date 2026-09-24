"""
Today page business logic — dispatch list and production list.

- Dispatch: orders fulfilling today, all non-cancelled statuses, per-order.
- Production: unfulfilled orders (CONFIRMED/IN_PROGRESS) fulfilling in
  the next 7 days, aggregated by SKU into three buckets.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Order, OrderItem, OrderStatus, Product
from app.utils.time import business_today_bounds_utc


def dispatch_today(db: Session) -> list[Order]:
    """Orders fulfilling today (business timezone), sorted by fulfillment time."""
    today_start, today_end = business_today_bounds_utc()

    query = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.payments))
        .where(
            Order.fulfillment_date >= today_start,
            Order.fulfillment_date <= today_end,
            Order.status != OrderStatus.CANCELLED,
        )
        .order_by(Order.fulfillment_date.asc())
    )
    return list(db.execute(query).scalars().all())


def production_this_week(db: Session, days: int = 7) -> dict:
    """
    Aggregate production needs for unfulfilled orders.

    Returns {
        "urgent":   [ {sku, name, measure, pack, qty, order_count, earliest, prep_hours}, ... ],
        "tomorrow": [ ... ],
        "later":    [ ... ],
        "total_units": int,
    }
    """
    today_start, today_end = business_today_bounds_utc()
    tomorrow_end = today_end + timedelta(days=1)
    horizon_end = today_start + timedelta(days=days)

    query = (
        select(OrderItem, Order, Product)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(
            Order.status.in_([OrderStatus.CONFIRMED, OrderStatus.IN_PROGRESS]),
            Order.fulfillment_date >= today_start,
            Order.fulfillment_date < horizon_end,
        )
        .order_by(Order.fulfillment_date.asc())
    )

    rows = db.execute(query).all()

    # bucket key = ("urgent" | "tomorrow" | "later", product_id)
    agg: dict[tuple[str, int], dict] = {}
    order_ids_per_key: dict[tuple[str, int], set[int]] = {}

    for item, order, product in rows:
        if order.fulfillment_date <= today_end:
            bucket = "urgent"
        elif order.fulfillment_date <= tomorrow_end:
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
    tomorrow = _sorted("tomorrow")
    later = _sorted("later")

    return {
        "urgent": urgent,
        "tomorrow": tomorrow,
        "later": later,
        "total_units": sum(r["qty"] for r in urgent + tomorrow + later),
    }
