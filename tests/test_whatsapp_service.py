"""Tests for WhatsApp link building and phone normalization."""

import json
from pathlib import Path

from app.services.whatsapp_service import (
    build_wa_url,
    load_messages,
    messages_for_order,
    normalize_phone,
    render_message,
)

# ---------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------


def test_normalize_10_digit_prepends_cc():
    assert normalize_phone("9876543210") == "919876543210"


def test_normalize_with_plus_and_spaces():
    assert normalize_phone("+91 98765 43210") == "919876543210"


def test_normalize_with_leading_zero():
    assert normalize_phone("09876543210") == "919876543210"


def test_normalize_already_has_cc():
    assert normalize_phone("919876543210") == "919876543210"


def test_normalize_empty():
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""


def test_normalize_too_short():
    assert normalize_phone("12345") == ""


def test_normalize_custom_country_code():
    assert normalize_phone("9876543210", default_cc="1") == "19876543210"


# ---------------------------------------------------------------
# URL building
# ---------------------------------------------------------------


def test_build_url_encodes_message():
    url = build_wa_url("919876543210", "Hi Priya, order #1 is ready.")
    assert url.startswith("https://wa.me/919876543210?text=")
    assert "Priya" in url or "%20" in url  # URL-encoded


# ---------------------------------------------------------------
# Message loading
# ---------------------------------------------------------------


def test_load_defaults_when_file_missing():
    msgs = load_messages("/nonexistent/path.json")
    assert "ready" in msgs
    assert "confirmed" in msgs


def test_load_overrides_merge(tmp_path: Path):
    p = tmp_path / "messages.json"
    p.write_text(json.dumps({"ready": "Custom ready message"}), encoding="utf-8")
    msgs = load_messages(str(p))
    assert msgs["ready"] == "Custom ready message"
    # Non-overridden keys still present
    assert "confirmed" in msgs


# ---------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------


def test_render_missing_variable_is_blank():
    out = render_message(
        "Hi {customer_first_name}, xyz {unknown_var}!", {"customer_first_name": "Priya"}
    )
    assert "Priya" in out
    assert "!" in out


def test_render_unbalanced_braces_returns_raw():
    out = render_message("Bad { template", {"x": 1})
    assert out == "Bad { template"


# ---------------------------------------------------------------
# messages_for_order
# ---------------------------------------------------------------


def test_messages_for_order_full_set(db, customer, product):
    from app.services.order_service import create_order

    o = create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": 1}],
            "fulfillment_date": "2026-12-31T12:00",
            "delivery_type": "DELIVERY",
            "delivery_address": "Test St",
        },
    )
    msgs = messages_for_order(o)
    keys = {m["key"] for m in msgs}
    assert "confirmed" in keys
    assert "ready" in keys
    assert "out_for_delivery" in keys
    assert "delivered" in keys
    assert "payment_reminder" in keys  # balance > 0
    assert "custom" in keys


def test_messages_exclude_out_for_delivery_when_pickup(db, customer, product):
    from app.services.order_service import create_order

    o = create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": 1}],
            "fulfillment_date": "2026-12-31T12:00",
            "delivery_type": "PICKUP",
        },
    )
    msgs = messages_for_order(o)
    keys = {m["key"] for m in msgs}
    assert "out_for_delivery" not in keys
    assert "ready" in keys


def test_messages_omit_payment_reminder_when_paid(db, customer, product):
    from app.services.order_service import create_order, record_payment

    o = create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": 1}],
            "fulfillment_date": "2026-12-31T12:00",
        },
    )
    record_payment(db, o.id, o.balance_due, "CASH", None)
    db.refresh(o)

    msgs = messages_for_order(o)
    keys = {m["key"] for m in msgs}
    assert "payment_reminder" not in keys


def test_messages_empty_when_phone_invalid(db, customer, product):
    from app.services.order_service import create_order

    # Set the customer's phone to garbage
    customer.phone = "abc"
    db.commit()

    o = create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": 1}],
            "fulfillment_date": "2026-12-31T12:00",
        },
    )
    msgs = messages_for_order(o)
    assert msgs == []
