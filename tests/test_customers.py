"""Tests for customer CRUD + addresses."""

from app.models import Customer, Address


def test_create_customer(client, db_session):
    client.post("/customers", data={
        "name": "Priya Sharma",
        "phone": "+91 98765 43210",
        "email": "priya@example.com",
        "notes": "Allergic to nuts",
        "addr_new_label": ["Home"],
        "addr_new_line": ["Flat 12, Andheri West, Mumbai"],
        "addr_new_default": ["1"],
    })
    customer = db_session.query(Customer).filter_by(phone="+91 98765 43210").first()
    assert customer is not None
    assert customer.name == "Priya Sharma"
    # Address should be created
    active_addrs = [a for a in customer.addresses if a.is_active]
    assert len(active_addrs) == 1
    assert active_addrs[0].label == "Home"
    assert active_addrs[0].is_default is True


def test_create_customer_multiple_addresses(client, db_session):
    """Add 2 addresses at once, only first 'Def' wins."""
    client.post("/customers", data={
        "name": "Multi Addr",
        "phone": "+91 44444 55555",
        "email": "",
        "notes": "",
        "addr_new_label": ["Home", "Office"],
        "addr_new_line": ["1 Home St", "2 Office Rd"],
        "addr_new_default": ["1", "1"],  # Both marked, first wins
    })
    customer = db_session.query(Customer).filter_by(phone="+91 44444 55555").first()
    active_addrs = [a for a in customer.addresses if a.is_active]
    assert len(active_addrs) == 2
    defaults = [a for a in active_addrs if a.is_default]
    assert len(defaults) == 1
    assert defaults[0].label == "Home"


def test_create_customer_without_address(client, db_session):
    client.post("/customers", data={
        "name": "No Addr",
        "phone": "+91 88888 77777",
        "email": "",
        "notes": "",
        "addr_new_label": ["Home"],
        "addr_new_line": [""],
        "addr_new_default": [""],
    })
    customer = db_session.query(Customer).filter_by(phone="+91 88888 77777").first()
    assert customer is not None
    active_addrs = [a for a in customer.addresses if a.is_active]
    assert len(active_addrs) == 0


def test_list_customers(client, db_session):
    client.post("/customers", data={
        "name": "Rahul", "phone": "+91 11111 22222",
        "email": "", "notes": "",
        "addr_new_label": ["Home"], "addr_new_line": [""], "addr_new_default": [""],
    })
    resp = client.get("/customers")
    assert resp.status_code == 200
    assert "Rahul" in resp.text


def test_duplicate_phone_rejected(client, db_session):
    data = {
        "name": "A", "phone": "+91 55555 66666", "email": "", "notes": "",
        "addr_new_label": ["Home"], "addr_new_line": [""], "addr_new_default": [""],
    }
    client.post("/customers", data=data)
    assert db_session.query(Customer).filter_by(phone="+91 55555 66666").first() is not None

    client.post("/customers", data={**data, "name": "B"})
    active = db_session.query(Customer).filter_by(
        Customer.phone == "+91 55555 66666", Customer.is_active == True
    ).count()
    assert active == 1


def test_customer_detail_shows_addresses(client, db_session, sample_customer):
    resp = client.get(f"/customers/{sample_customer.id}")
    assert resp.status_code == 200
    assert "Test Customer" in resp.text
    assert "Addresses" in resp.text
    assert "123 Test Street" in resp.text


def test_edit_customer(client, db_session):
    client.post("/customers", data={
        "name": "Old Name", "phone": "+91 77777 88888",
        "email": "", "notes": "",
        "addr_new_label": ["Home"], "addr_new_line": [""], "addr_new_default": [""],
    })
    customer = db_session.query(Customer).filter_by(phone="+91 77777 88888").first()

    client.post(f"/customers/{customer.id}/edit", data={
        "name": "New Name", "phone": "+91 77777 88888",
        "email": "new@example.com", "notes": "Updated",
        "addr_new_label": ["Office"],
        "addr_new_line": ["567 Office Park, Bangalore"],
        "addr_new_default": ["1"],
    })
    db_session.refresh(customer)
    assert customer.name == "New Name"
    assert customer.email == "new@example.com"
    active_addrs = [a for a in customer.addresses if a.is_active]
    assert len(active_addrs) == 1
    assert active_addrs[0].label == "Office"


def test_set_default_via_ajax(client, db_session, sample_customer):
    """Set default via the AJAX endpoint."""
    # Add a second address
    client.post(f"/customers/{sample_customer.id}/edit", data={
        "name": "Test Customer", "phone": "+91 99999 99999",
        "email": "test@example.com", "notes": "",
        "addr_new_label": ["Office"],
        "addr_new_line": ["567 Office Park"],
        "addr_new_default": [""],
    })
    db_session.refresh(sample_customer)
    active_addrs = [a for a in sample_customer.addresses if a.is_active]
    assert len(active_addrs) == 2

    # Set the second one as default
    office = [a for a in active_addrs if a.label == "Office"][0]
    resp = client.post(f"/customers/{sample_customer.id}/addresses/{office.id}/set-default")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    db_session.refresh(sample_customer)
    active_addrs = [a for a in sample_customer.addresses if a.is_active]
    defaults = [a for a in active_addrs if a.is_default]
    assert len(defaults) == 1
    assert defaults[0].label == "Office"


def test_soft_delete_address_via_ajax(client, db_session, sample_customer):
    """Soft delete via the AJAX endpoint."""
    addr_id = [a for a in sample_customer.addresses if a.is_active][0].id
    resp = client.post(f"/customers/{sample_customer.id}/addresses/{addr_id}/delete")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    db_session.refresh(sample_customer)
    active_addrs = [a for a in sample_customer.addresses if a.is_active]
    assert len(active_addrs) == 0


def test_soft_delete_customer(client, db_session, sample_customer):
    """Soft delete customer cascades to addresses."""
    assert len([a for a in sample_customer.addresses if a.is_active]) == 1

    resp = client.post(f"/customers/{sample_customer.id}/delete")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    db_session.refresh(sample_customer)
    assert sample_customer.is_active is False
    active_addrs = [a for a in sample_customer.addresses if a.is_active]
    assert len(active_addrs) == 0  # Addresses also soft-deleted


def test_deleted_customer_excluded_from_search(client, db_session, sample_customer):
    client.post(f"/customers/{sample_customer.id}/delete")
    resp = client.get("/customers/search?q=Test")
    assert resp.status_code == 200
    assert "Test Customer" not in resp.text


def test_customer_search_by_name(client, db_session, sample_customer):
    resp = client.get("/customers/search?q=Test")
    assert resp.status_code == 200
    assert "Test Customer" in resp.text


def test_customer_search_by_phone(client, db_session, sample_customer):
    resp = client.get("/customers/search?q=99999")
    assert resp.status_code == 200
    assert "Test Customer" in resp.text


def test_customer_search_too_short(client, db_session, sample_customer):
    resp = client.get("/customers/search?q=T")
    assert resp.status_code == 200
    assert "Test Customer" not in resp.text


def test_empty_state(client):
    resp = client.get("/customers")
    assert resp.status_code == 200
    assert "Customers" in resp.text

def test_duplicate_phone_rejected(client, db_session):
    data = {
        "name": "A", "phone": "+91 55555 66666", "email": "", "notes": "",
        "addr_new_label": ["Home"], "addr_new_line": [""], "addr_new_default": [""],
    }
    client.post("/customers", data=data)
    db_session.expire_all()  # ← ADD
    assert db_session.query(Customer).filter_by(phone="+91 55555 66666").first() is not None

    client.post("/customers", data={**data, "name": "B"})
    db_session.expire_all()  # ← ADD
    active = db_session.query(Customer).filter_by(
        phone="+91 55555 66666", is_active=True
    ).count()
    assert active == 1