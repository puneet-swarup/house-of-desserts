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


def test_generate_endpoint_accepts_form_post(client, db_session, customer, product):
    """Regression: form POST must send year/month as form fields, not querystring."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.config import get_settings
    from app.services.order_service import create_order

    tz = ZoneInfo(get_settings().business_timezone)
    dt_local = datetime(2026, 9, 15, 12, 0, tzinfo=tz)
    create_order(
        db_session,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": 1}],
            "fulfillment_date": dt_local.isoformat(),
            "order_date": dt_local.date().isoformat(),
        },
    )
    db_session.commit()

    # POST with form-encoded body, not querystring
    resp = client.post(
        "/reports/generate",
        data={"year": "2026", "month": "9"},
        follow_redirects=False,
    )
    # 303 redirect to /reports?generated=2026-09
    assert resp.status_code == 303
    assert "generated=2026-09" in resp.headers["location"]


def test_reports_page_loads(client):
    resp = client.get("/reports")
    assert resp.status_code == 200
    assert "Monthly Reports" in resp.text


def test_reports_download_endpoint(client, db_session, customer, product, tmp_path, monkeypatch):
    """Generate a report, then download it via the HTTP endpoint."""
    import app.services.reports_service as rs

    monkeypatch.setattr(rs, "_reports_dir", lambda: tmp_path)

    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.config import get_settings
    from app.services.order_service import create_order

    tz = ZoneInfo(get_settings().business_timezone)
    dt_local = datetime(2026, 9, 15, 12, 0, tzinfo=tz)
    create_order(
        db_session,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": 1}],
            "fulfillment_date": dt_local.isoformat(),
            "order_date": dt_local.date().isoformat(),
        },
    )
    db_session.commit()

    rs.generate_report(db_session, 2026, 9)

    resp = client.get("/reports/download/2026-09.csv")
    assert resp.status_code == 200
    assert "Monthly Report" in resp.text

    resp_pdf = client.get("/reports/download/2026-09.pdf")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"


def test_download_rejects_path_traversal(client):
    resp = client.get("/reports/download/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (400, 404)
