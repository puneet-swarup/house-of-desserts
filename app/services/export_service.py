"""
Export service — CSV/JSON for tax filing.

All amounts come from stored Decimal columns. No recomputation of
GST from rates; we trust what was written at order time.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Order, OrderStatus
from app.utils.money import money
from app.utils.time import business_day_bounds_utc


def _bounds(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    start, _ = business_day_bounds_utc(start_date)
    _, end = business_day_bounds_utc(end_date)
    return start, end


def export_orders_csv(db: Session, start_date: str, end_date: str) -> tuple[str, str]:
    start, end = _bounds(start_date, end_date)

    orders = db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.order_date >= start, Order.order_date <= end)
        .where(Order.status != OrderStatus.CANCELLED)
        .order_by(Order.order_date)
    ).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Order Number", "Date", "Customer", "Phone", "Status",
        "Delivery Type", "Subtotal", "GST Amount", "Total",
        "Advance Paid", "Balance Due", "Items",
    ])

    for order in orders:
        gst_total = sum((money(i.gst_amount) for i in order.items), Decimal("0.00"))
        subtotal = money(order.total_amount - gst_total)
        items_str = "; ".join(
            f"{i.product.name} x{i.quantity}" for i in order.items
        )
        writer.writerow([
            order.order_number,
            order.order_date.strftime("%Y-%m-%d %H:%M"),
            order.customer.name,
            order.customer.phone,
            order.status.value,
            order.delivery_type,
            f"{subtotal:.2f}",
            f"{gst_total:.2f}",
            f"{money(order.total_amount):.2f}",
            f"{money(order.advance_paid):.2f}",
            f"{money(order.balance_due):.2f}",
            items_str,
        ])

    return f"orders_{start_date}_to_{end_date}.csv", output.getvalue()


def export_payments_csv(db: Session, start_date: str, end_date: str) -> tuple[str, str]:
    start, end = _bounds(start_date, end_date)

    orders = db.execute(
        select(Order)
        .options(selectinload(Order.payments), selectinload(Order.customer))
        .where(Order.order_date >= start, Order.order_date <= end)
        .order_by(Order.order_date)
    ).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Order Number", "Customer", "Payment Date", "Amount",
        "Method", "Reference", "Running Total Paid",
    ])

    for order in orders:
        running = Decimal("0.00")
        for p in order.payments:
            if start <= p.received_at <= end:
                running += money(p.amount)
                writer.writerow([
                    order.order_number,
                    order.customer.name,
                    p.received_at.strftime("%Y-%m-%d %H:%M"),
                    f"{money(p.amount):.2f}",
                    p.method,
                    p.reference or "",
                    f"{running:.2f}",
                ])

    return f"payments_{start_date}_to_{end_date}.csv", output.getvalue()


def export_summary_json(db: Session, start_date: str, end_date: str) -> tuple[str, str]:
    start, end = _bounds(start_date, end_date)

    orders = db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.order_date >= start, Order.order_date <= end)
        .where(Order.status != OrderStatus.CANCELLED)
    ).scalars().all()

    total_revenue = sum((money(o.total_amount) for o in orders), Decimal("0.00"))
    total_gst = sum(
        (sum((money(i.gst_amount) for i in o.items), Decimal("0.00")) for o in orders),
        Decimal("0.00"),
    )
    total_collected = sum((money(o.advance_paid) for o in orders), Decimal("0.00"))
    total_outstanding = sum((money(o.balance_due) for o in orders), Decimal("0.00"))

    by_status: dict[str, int] = {}
    for o in orders:
        by_status[o.status.value] = by_status.get(o.status.value, 0) + 1

    product_sales: dict[str, Decimal] = {}
    for o in orders:
        for item in o.items:
            name = item.product.name
            product_sales[name] = product_sales.get(name, Decimal("0.00")) + money(item.line_total)

    top = sorted(product_sales.items(), key=lambda kv: kv[1], reverse=True)[:10]

    summary = {
        "period": {"start": start_date, "end": end_date},
        "total_orders": len(orders),
        "total_revenue": str(money(total_revenue)),
        "total_gst_collected": str(money(total_gst)),
        "total_amounts_collected": str(money(total_collected)),
        "total_outstanding": str(money(total_outstanding)),
        "orders_by_status": by_status,
        "top_products": [{"name": n, "revenue": str(money(r))} for n, r in top],
    }
    return f"summary_{start_date}_to_{end_date}.json", json.dumps(summary, indent=2)
