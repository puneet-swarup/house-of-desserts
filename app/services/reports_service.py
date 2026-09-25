"""
Monthly reports — PDF (for reading/printing) and CSV (for Excel/CA).

A report for month M covers orders whose order_date falls within M in
the BUSINESS timezone. order_date is stored as naive UTC, so we convert
the business-tz month bounds to UTC before filtering.

Output files (regenerating overwrites):
    <reports_dir>/2026-09.pdf
    <reports_dir>/2026-09.csv

Called from:
  - POST /reports/generate         (manual, in-app)
  - scripts/monthly_report.py      (cron, 1st of month for previous month)

Reports are regenerable summaries, not immutable documents. If you need
a frozen version, copy the PDF elsewhere.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import Order, OrderStatus
from app.utils.money import money

MONTH_NAMES = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def _month_bounds_utc(year: int, month: int) -> tuple[datetime, datetime]:
    """
    Return (start_utc, end_utc) as naive UTC datetimes for filtering
    against Order.order_date. Month is interpreted in business timezone.
    """
    settings = get_settings()
    tz = ZoneInfo(settings.business_timezone)

    local_start = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=tz)
    local_end = next_month - timedelta(microseconds=1)

    return (
        local_start.astimezone(tz).astimezone(ZoneInfo("UTC")).replace(tzinfo=None),
        local_end.astimezone(ZoneInfo("UTC")).replace(tzinfo=None),
    )


def _reports_dir() -> Path:
    settings = get_settings()
    p = Path(settings.reports_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def report_filename(year: int, month: int, ext: str) -> str:
    return f"{year}-{month:02d}.{ext}"


def report_path(year: int, month: int, ext: str) -> Path:
    return _reports_dir() / report_filename(year, month, ext)


# ---------------------------------------------------------------
# Data gathering
# ---------------------------------------------------------------


def build_report(db: Session, year: int, month: int) -> dict:
    """
    Return a dict with all data needed to render a month's report.
    Includes cancelled orders in a separate count but excludes them
    from revenue.
    """
    start_utc, end_utc = _month_bounds_utc(year, month)

    # All orders in the window (including cancelled, for the count)
    all_orders = (
        db.execute(
            select(Order)
            .options(selectinload(Order.items), selectinload(Order.customer))
            .where(Order.order_date >= start_utc, Order.order_date <= end_utc)
            .order_by(Order.order_date.asc())
        )
        .scalars()
        .all()
    )

    active_orders = [o for o in all_orders if o.status != OrderStatus.CANCELLED]

    total_revenue = Decimal("0.00")
    total_gst = Decimal("0.00")
    total_received = Decimal("0.00")
    total_outstanding = Decimal("0.00")

    for o in active_orders:
        total_revenue += money(o.total_amount)
        total_received += money(o.advance_paid)
        total_outstanding += money(o.balance_due)
        for it in o.items:
            total_gst += money(it.gst_amount)

    # Status breakdown (all orders, including cancelled)
    by_status: dict[str, int] = {}
    for o in all_orders:
        by_status[o.status.value] = by_status.get(o.status.value, 0) + 1

    # Payment state breakdown for non-cancelled
    by_payment: dict[str, int] = {"paid": 0, "partial": 0, "unpaid": 0}
    for o in active_orders:
        by_payment[o.payment_state] = by_payment.get(o.payment_state, 0) + 1

    # Top products by revenue (non-cancelled)
    product_sales: dict[int, dict] = {}
    for o in active_orders:
        for it in o.items:
            pid = it.product_id
            if pid not in product_sales:
                product_sales[pid] = {
                    "sku": it.product.sku if it.product else "",
                    "name": it.product.name if it.product else "(deleted)",
                    "qty": 0,
                    "revenue": Decimal("0.00"),
                }
            product_sales[pid]["qty"] += it.quantity
            product_sales[pid]["revenue"] += money(it.line_total)

    top_products = sorted(
        product_sales.values(),
        key=lambda r: r["revenue"],
        reverse=True,
    )[:10]

    # Itemized list — same order as all_orders but flat
    itemized: list[dict] = []
    for o in active_orders:
        itemized.append(
            {
                "order_number": o.order_number,
                "order_date": o.order_date,
                "customer_name": o.customer.name if o.customer else "",
                "customer_phone": o.customer.phone if o.customer else "",
                "status": o.status.value,
                "payment_state": o.payment_state,
                "total": money(o.total_amount),
                "gst": sum((money(it.gst_amount) for it in o.items), Decimal("0.00")),
                "paid": money(o.advance_paid),
                "balance": money(o.balance_due),
            }
        )

    return {
        "year": year,
        "month": month,
        "period_label": f"{MONTH_NAMES[month]} {year}",
        "generated_at": datetime.now(),
        "orders_total": len(all_orders),
        "orders_active": len(active_orders),
        "orders_cancelled": by_status.get("CANCELLED", 0),
        "total_revenue": money(total_revenue),
        "total_gst": money(total_gst),
        "total_received": money(total_received),
        "total_outstanding": money(total_outstanding),
        "average_order_value": (
            money(total_revenue / len(active_orders)) if active_orders else Decimal("0.00")
        ),
        "by_status": by_status,
        "by_payment": by_payment,
        "top_products": top_products,
        "itemized": itemized,
    }


# ---------------------------------------------------------------
# CSV rendering
# ---------------------------------------------------------------


def render_csv(report: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)

    w.writerow(["Monthly Report", report["period_label"]])
    w.writerow(["Generated", report["generated_at"].strftime("%Y-%m-%d %H:%M")])
    w.writerow([])

    w.writerow(["Summary"])
    w.writerow(["Orders (total)", report["orders_total"]])
    w.writerow(["Orders (non-cancelled)", report["orders_active"]])
    w.writerow(["Orders cancelled", report["orders_cancelled"]])
    w.writerow(["Revenue", f"{report['total_revenue']:.2f}"])
    w.writerow(["GST collected", f"{report['total_gst']:.2f}"])
    w.writerow(["Amount received", f"{report['total_received']:.2f}"])
    w.writerow(["Outstanding", f"{report['total_outstanding']:.2f}"])
    w.writerow(["Average order value", f"{report['average_order_value']:.2f}"])
    w.writerow([])

    w.writerow(["Orders by status"])
    for status, count in sorted(report["by_status"].items()):
        w.writerow([status, count])
    w.writerow([])

    w.writerow(["Orders by payment state"])
    for state, count in report["by_payment"].items():
        w.writerow([state, count])
    w.writerow([])

    w.writerow(["Top products"])
    w.writerow(["SKU", "Name", "Quantity", "Revenue"])
    for p in report["top_products"]:
        w.writerow([p["sku"], p["name"], p["qty"], f"{p['revenue']:.2f}"])
    w.writerow([])

    w.writerow(["Itemized orders"])
    w.writerow(
        [
            "Order Number",
            "Date",
            "Customer",
            "Phone",
            "Status",
            "Payment",
            "Total",
            "GST",
            "Paid",
            "Balance",
        ]
    )
    for row in report["itemized"]:
        w.writerow(
            [
                row["order_number"],
                row["order_date"].strftime("%Y-%m-%d %H:%M"),
                row["customer_name"],
                row["customer_phone"],
                row["status"],
                row["payment_state"],
                f"{row['total']:.2f}",
                f"{row['gst']:.2f}",
                f"{row['paid']:.2f}",
                f"{row['balance']:.2f}",
            ]
        )

    return out.getvalue()


# ---------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------


def _fmt_money(v) -> str:
    settings = get_settings()
    return f"{settings.currency}{v:,.2f}"


def render_pdf(report: dict, output_path: Path) -> None:
    """
    Render the monthly report as PDF using fpdf2. Uses Noto Sans if the
    font files are present (supports the ₹ symbol); falls back to
    Helvetica and 'Rs. ' otherwise.
    """
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    settings = get_settings()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    font_dir = Path(__file__).parent.parent / "static" / "fonts"
    use_unicode = (font_dir / "NotoSans-Regular.ttf").exists()
    if use_unicode:
        pdf.add_font("Noto", "", str(font_dir / "NotoSans-Regular.ttf"))
        pdf.add_font("Noto", "B", str(font_dir / "NotoSans-Bold.ttf"))
        font = "Noto"
        sym = settings.currency
    else:
        font = "Helvetica"
        sym = "Rs. "

    def money_str(v) -> str:
        return f"{sym}{v:,.2f}"

    # Header
    pdf.set_font(font, "B", 16)
    pdf.cell(0, 10, settings.app_name, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font(font, "", 9)
    for line in (
        settings.address,
        settings.phone,
        f"GSTIN: {settings.gstin}" if settings.gstin else "",
        f"FSSAI: {settings.fssai_number}" if settings.fssai_number else "",
    ):
        if line:
            pdf.cell(0, 4, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    pdf.ln(4)
    pdf.set_font(font, "B", 14)
    pdf.cell(
        0,
        8,
        f"Monthly Report - {report['period_label']}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.set_font(font, "", 9)
    pdf.cell(
        0,
        5,
        f"Generated {report['generated_at'].strftime('%d %b %Y %H:%M')}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.ln(6)

    # Summary
    pdf.set_font(font, "B", 11)
    pdf.cell(0, 7, "Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(font, "", 10)

    summary_rows = [
        ("Orders (non-cancelled)", str(report["orders_active"])),
        ("Orders cancelled", str(report["orders_cancelled"])),
        ("Revenue", money_str(report["total_revenue"])),
        ("GST collected", money_str(report["total_gst"])),
        ("Amount received", money_str(report["total_received"])),
        ("Outstanding", money_str(report["total_outstanding"])),
        ("Average order value", money_str(report["average_order_value"])),
    ]
    for label, value in summary_rows:
        pdf.cell(100, 6, label, border=0)
        pdf.cell(0, 6, value, border=0, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # Status breakdown
    pdf.set_font(font, "B", 11)
    pdf.cell(0, 7, "Orders by status", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(font, "", 10)
    for status, count in sorted(report["by_status"].items()):
        pdf.cell(100, 6, status, border=0)
        pdf.cell(0, 6, str(count), border=0, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # Top products
    if report["top_products"]:
        pdf.set_font(font, "B", 11)
        pdf.cell(0, 7, "Top products by revenue", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font(font, "B", 9)
        pdf.cell(30, 6, "SKU", border=1)
        pdf.cell(95, 6, "Name", border=1)
        pdf.cell(20, 6, "Qty", border=1, align="R")
        pdf.cell(45, 6, "Revenue", border=1, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font(font, "", 9)
        for p in report["top_products"]:
            name = p["name"]
            if len(name) > 50:
                name = name[:47] + "..."
            pdf.cell(30, 6, p["sku"][:20], border=1)
            pdf.cell(95, 6, name, border=1)
            pdf.cell(20, 6, str(p["qty"]), border=1, align="R")
            pdf.cell(
                45,
                6,
                money_str(p["revenue"]),
                border=1,
                align="R",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
        pdf.ln(6)

    # Itemized
    pdf.set_font(font, "B", 11)
    pdf.cell(0, 7, "Itemized orders", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if not report["itemized"]:
        pdf.set_font(font, "", 10)
        pdf.cell(0, 6, "No orders in this period.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        pdf.set_font(font, "B", 8)
        cols = [
            ("Order", 32),
            ("Date", 24),
            ("Customer", 40),
            ("Status", 22),
            ("Pay", 16),
            ("Total", 24),
            ("Balance", 22),
        ]
        for label, w in cols:
            pdf.cell(w, 6, label, border=1)
        pdf.ln()

        pdf.set_font(font, "", 8)
        for row in report["itemized"]:
            cust = row["customer_name"]
            if len(cust) > 22:
                cust = cust[:20] + ".."
            pdf.cell(32, 5, row["order_number"], border=1)
            pdf.cell(24, 5, row["order_date"].strftime("%d %b %Y"), border=1)
            pdf.cell(40, 5, cust, border=1)
            pdf.cell(22, 5, row["status"], border=1)
            pdf.cell(16, 5, row["payment_state"], border=1)
            pdf.cell(24, 5, money_str(row["total"]), border=1, align="R")
            pdf.cell(
                22,
                5,
                money_str(row["balance"]),
                border=1,
                align="R",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))


# ---------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------


def generate_report(db: Session, year: int, month: int) -> dict:
    """
    Build the report data, write both PDF and CSV, return paths + summary.
    """
    if not (1 <= month <= 12):
        raise ValueError(f"month must be 1..12, got {month}")

    report = build_report(db, year, month)

    csv_path = report_path(year, month, "csv")
    csv_path.write_text(render_csv(report), encoding="utf-8")

    pdf_path = report_path(year, month, "pdf")
    render_pdf(report, pdf_path)

    return {
        "year": year,
        "month": month,
        "period_label": report["period_label"],
        "csv_path": str(csv_path),
        "pdf_path": str(pdf_path),
        "orders_active": report["orders_active"],
        "total_revenue": report["total_revenue"],
    }


def list_existing_reports() -> list[dict]:
    """Scan the reports dir and return metadata for each month found."""
    d = _reports_dir()
    by_month: dict[str, dict] = {}
    for f in sorted(d.iterdir()):
        if f.suffix not in (".pdf", ".csv"):
            continue
        stem = f.stem  # e.g. "2026-09"
        parts = stem.split("-")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        y, m = int(parts[0]), int(parts[1])
        if not (1 <= m <= 12):
            continue
        entry = by_month.setdefault(
            stem,
            {
                "year": y,
                "month": m,
                "period_label": f"{MONTH_NAMES[m]} {y}",
                "pdf": False,
                "csv": False,
                "generated_at": f.stat().st_mtime,
            },
        )
        if f.suffix == ".pdf":
            entry["pdf"] = True
        elif f.suffix == ".csv":
            entry["csv"] = True
        entry["generated_at"] = max(entry["generated_at"], f.stat().st_mtime)

    out = list(by_month.values())
    out.sort(key=lambda r: (r["year"], r["month"]), reverse=True)
    for r in out:
        r["generated_at"] = datetime.fromtimestamp(r["generated_at"])
    return out
