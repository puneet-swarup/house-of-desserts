"""Tests for audit log."""

from app.models import AuditLog


def test_create_product_logged(client, db_session, sample_product):
    logs = db_session.query(AuditLog).filter_by(entity_type="Product").all()
    assert len(logs) >= 1
    assert any(l.action == "CREATE" for l in logs)


def test_create_customer_logged(client, db_session, sample_customer):
    logs = db_session.query(AuditLog).filter_by(entity_type="Customer").all()
    assert len(logs) >= 1
    assert any(l.action == "CREATE" for l in logs)


def test_status_change_logged(client, db_session, sample_order):
    client.post(f"/orders/{sample_order.id}/status", data={"status": "IN_PROGRESS"})
    logs = db_session.query(AuditLog).filter_by(
        entity_type="Order", action="STATUS_CHANGE"
    ).all()
    assert len(logs) >= 1


def test_payment_logged(client, db_session, sample_order):
    client.post(f"/orders/{sample_order.id}/payments", data={
        "amount": "50.00", "method": "CASH", "reference": "",
    })
    logs = db_session.query(AuditLog).filter_by(action="PAYMENT").all()
    assert len(logs) >= 1


def test_audit_page_renders(client, db_session):
    resp = client.get("/audit")
    assert resp.status_code == 200
    assert "Audit Log" in resp.text


def test_audit_filter_by_entity(client, db_session, sample_order):
    resp = client.get("/audit?entity=Order")
    assert resp.status_code == 200
    assert "Order" in resp.text
