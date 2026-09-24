"""Tests for invoice generation and printing."""

import importlib.util

import pytest

from app.models import Order

fpdf_available = importlib.util.find_spec('fpdf') is not None


def test_view_invoice_preview(client, db_session, sample_order):
    resp = client.get(f"/invoices/orders/{sample_order.id}/invoice")
    assert resp.status_code == 200
    assert "Invoice Preview" in resp.text
    assert "TAX INVOICE" in resp.text


def test_invoice_shows_delivery_address(client, db_session, sample_order):
    resp = client.get(f"/invoices/orders/{sample_order.id}/invoice")
    assert resp.status_code == 200
    assert "Deliver To" in resp.text
    assert "123 Test Street" in resp.text


def test_invoice_pickup_shows_pickup_label(client, db_session, sample_customer, sample_product):
    client.post("/orders", data={
        "customer_id": str(sample_customer.id),
        "fulfillment_date": "2026-12-31T12:00",
        "delivery_type": "PICKUP",
        "delivery_date": "",
        "delivery_address": "",
        "notes": "",
        "advance_paid": "0",
        "advance_method": "UPI",
        "product_id": [str(sample_product.id)],
        "quantity": ["1"],
    })
    order = db_session.query(Order).filter_by(delivery_type="PICKUP").first()
    resp = client.get(f"/invoices/orders/{order.id}/invoice")
    assert resp.status_code == 200
    assert "Pickup" in resp.text


@pytest.mark.skipif(not fpdf_available, reason="fpdf2 not available")
def test_generate_pdf_creates_file(client, db_session, sample_order):
    resp = client.get(f"/invoices/orders/{sample_order.id}/generate-pdf")
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers.get("content-type", "")


def test_print_receipt(client, db_session, sample_order):
    resp = client.post(f"/invoices/orders/{sample_order.id}/print-receipt")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_print_receipt_includes_delivery_address(client, db_session, sample_order):
    from pathlib import Path
    client.post(f"/invoices/orders/{sample_order.id}/print-receipt")
    bin_file = Path("data/receipt_preview.bin")
    assert bin_file.exists()
    content = bin_file.read_bytes().decode("latin-1")
    assert "123 Test Street" in content


def test_invoice_number_sequential(client, db_session, sample_order):
    from app.services import invoice_service
    invoice = invoice_service.create_invoice(db_session, sample_order.id)
    assert invoice.invoice_number.endswith("-0001")
