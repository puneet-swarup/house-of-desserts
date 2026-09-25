"""Tests for monthly reports."""

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.config import get_settings
from app.models import OrderStatus
from app.services import reports_service
from app.services.order_service import create_order, record_payment, update_status


def _order_in_month(db, customer, product, year, month, day=15, qty=1, advance=0, cancel=False):
    tz = ZoneInfo(get_settings().business_timezone)
    dt_local = datetime(year, month, day, 12, 0, tzinfo=tz)
    fulfillment = dt_local.isoformat()
    order_date = dt_local.date().isoformat()

    o = create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": qty}],
            "fulfillment_date": fulfillment,
            "order_date": order_date,
            "advance_paid": advance,
        },
    )
    if cancel:
        update_status(db, o.id, "CANCELLED")
    return o


def test_empty_month(db):
    report = reports_service.build_report(db, 2026, 9)
    assert report["orders_active"] == 0
    assert report["orders_cancelled"] == 0
    assert report["total_revenue"] == Decimal("0.00")


def test_summary_totals(db, customer, product):
    _order_in_month(db, customer, product, 2026, 9, day=5, qty=2)
    _order_in_month(db, customer, product, 2026, 9, day=10, qty=1)

    report = reports_service.build_report(db, 2026, 9)
    assert report["orders_active"] == 2
    assert report["total_revenue"] > Decimal("0.00")
    assert report["total_gst"] > Decimal("0.00")


def test_cancelled_orders_excluded_from_revenue(db, customer, product):
    _order_in_month(db, customer, product, 2026, 9, day=5, qty=2)
    _order_in_month(db, customer, product, 2026, 9, day=10, qty=5, cancel=True)

    report = reports_service.build_report(db, 2026, 9)
    assert report["orders_active"] == 1
    assert report["orders_cancelled"] == 1


def test_orders_outside_month_excluded(db, customer, product):
    _order_in_month(db, customer, product, 2026, 8, day=31)  # Aug
    _order_in_month(db, customer, product, 2026, 9, day=15)  # Sep

    report = reports_service.build_report(db, 2026, 9)
    assert report["orders_active"] == 1


def test_top_products_aggregates(db, customer, product):
    _order_in_month(db, customer, product, 2026, 9, day=5, qty=2)
    _order_in_month(db, customer, product, 2026, 9, day=10, qty=3)

    report = reports_service.build_report(db, 2026, 9)
    assert len(report["top_products"]) == 1
    assert report["top_products"][0]["qty"] == 5


def test_generate_writes_pdf_and_csv(db, customer, product, tmp_path, monkeypatch):
    # Patch the module-level function that resolves the reports directory.
    # Patching the settings object doesn't work reliably with lru_cache.
    monkeypatch.setattr(reports_service, "_reports_dir", lambda: tmp_path)

    _order_in_month(db, customer, product, 2026, 9, day=15, qty=2)

    reports_service.generate_report(db, 2026, 9)

    pdf = tmp_path / "2026-09.pdf"
    csv = tmp_path / "2026-09.csv"
    assert pdf.exists(), f"PDF missing at {pdf}"
    assert pdf.stat().st_size > 0, "PDF is empty"
    assert csv.exists(), f"CSV missing at {csv}"
    assert csv.stat().st_size > 0, "CSV is empty"

    csv_text = csv.read_text(encoding="utf-8")
    assert "Monthly Report" in csv_text
    assert "September 2026" in csv_text
    assert "Itemized orders" in csv_text
    assert customer.name in csv_text


def test_generate_rejects_bad_month(db):
    with pytest.raises(ValueError):
        reports_service.generate_report(db, 2026, 13)
