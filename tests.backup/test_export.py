"""Tests for CSV/JSON export."""

from datetime import datetime


def test_export_orders_csv(client, db_session, sample_order):
    db_session.commit()
    today = datetime.now().strftime("%Y-%m-%d")
    resp = client.get(f"/export/orders.csv?start=2020-01-01&end={today}")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "Order Number" in resp.text


def test_export_orders_includes_delivery_type(client, db_session, sample_order):
    db_session.commit()
    today = datetime.now().strftime("%Y-%m-%d")
    resp = client.get(f"/export/orders.csv?start=2020-01-01&end={today}")
    assert "DELIVERY" in resp.text


def test_export_payments_csv(client, db_session, sample_order):
    db_session.commit()
    today = datetime.now().strftime("%Y-%m-%d")
    resp = client.get(f"/export/payments.csv?start=2020-01-01&end={today}")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


def test_export_summary_json(client, db_session, sample_order):
    db_session.commit()
    today = datetime.now().strftime("%Y-%m-%d")
    resp = client.get(f"/export/summary.json?start=2020-01-01&end={today}")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_orders" in data
    assert data["total_orders"] >= 1


def test_export_empty_range(client):
    resp = client.get("/export/orders.csv?start=2020-01-01&end=2020-12-31")
    assert resp.status_code == 200
    assert "Order Number" in resp.text
