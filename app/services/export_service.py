"""
Export service — generates CSV/JSON files for tax filing and record-keeping.

Python concept: This service queries the DB for a date range and writes
a structured file. The user downloads it from the browser.
"""

import csv
import io
import json
from datetime import datetime
from typing import Generator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, Payment, OrderStatus


def export_orders_csv(db: Session, start_date: str, end_date: str) -> tuple[str, str]:
    """
    Export orders in a date range to CSV.
    Returns (filename, csv_content).

    start_date / end_date: "YYYY-MM-DD" format strings.
    """
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)

    orders = db.execute(
        select(Order)
        .where(Order.order_date >= start, Order.order_date <= end)
        .where(Order.status != OrderStatus.CANCELLED)
        .order_by(Order.order_date)
    ).scalars().all()

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Order Number", "Date", "Customer", "Phone", "Status",
        "Delivery Type", "Total Amount", "GST Amount", "Advance Paid",
        "Balance Due", "Items"
    ])

    for order in orders:
        gst_total = sum(item.gst_amount for item in order.items)
        items_str = "; ".join(
            f"{item.product.name} x{item.quantity}" for item in order.items
        )
        writer.writerow([
            order.order_number,
            order.order_date.strftime("%Y-%m-%d %H:%M"),
            order.customer.name,
            order.customer.phone,
            order.status.value,
            order.delivery_type,
            f"{order.total_amount:.2f}",
            f"{gst_total:.2f}",
            f"{order.advance_paid:.2f}",
            f"{order.balance_due:.2f}",
            items_str,
        ])

    filename = f"orders_{start_date}_to_{end_date}.csv"
    return filename, output.getvalue()


def export_payments_csv(db: Session, start_date: str, end_date: str) -> tuple[str, str]:
    """Export all payments in a date range to CSV."""
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)

    orders = db.execute(
        select(Order)
        .where(Order.order_date >= start, Order.order_date <= end)
        .order_by(Order.order_date)
    ).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Order Number", "Customer", "Payment Date", "Amount",
        "Method", "Reference", "Running Balance After"
    ])

    for order in orders:
        running = 0.0
        for p in order.payments:
            if start <= p.received_at <= end:
                running += p.amount
                writer.writerow([
                    order.order_number,
                    order.customer.name,
                    p.received_at.strftime("%Y-%m-%d %H:%M"),
                    f"{p.amount:.2f}",
                    p.method,
                    p.reference or "",
                    f"{order.total_amount - running:.2f}",
                ])

    filename = f"payments_{start_date}_to_{end_date}.csv"
    return filename, output.getvalue()


def export_summary_json(db: Session, start_date: str, end_date: str) -> tuple[str, str]:
    """Export a monthly summary as JSON (useful for ITR / CA)."""
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)

    orders = db.execute(
        select(Order)
        .where(Order.order_date >= start, Order.order_date <= end)
        .where(Order.status != OrderStatus.CANCELLED)
    ).scalars().all()

    total_revenue = sum(o.total_amount for o in orders)
    total_gst = sum(sum(i.gst_amount for i in o.items) for o in orders)
    total_collected = sum(o.advance_paid for o in orders)
    total_outstanding = sum(o.balance_due for o in orders)
    order_count = len(orders)

    # Breakdown by status
    by_status = {}
    for o in orders:
        s = o.status.value
        by_status[s] = by_status.get(s, 0) + 1

    # Top products
    product_sales = {}
    for o in orders:
        for item in o.items:
            name = item.product.name
            product_sales[name] = product_sales.get(name, 0) + item.line_total

    top_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:10]

    summary = {
        "period": {"start": start_date, "end": end_date},
        "total_orders": order_count,
        "total_revenue": round(total_revenue, 2),
        "total_gst_collected": round(total_gst, 2),
        "total_amounts_collected": round(total_collected, 2),
        "total_outstanding": round(total_outstanding, 2),
        "orders_by_status": by_status,
        "top_products": [{"name": n, "revenue": round(r, 2)} for n, r in top_products],
    }

    filename = f"summary_{start_date}_to_{end_date}.json"
    return filename, json.dumps(summary, indent=2)   