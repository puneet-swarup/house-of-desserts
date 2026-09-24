"""
Shared pytest fixtures.

- Single in-memory SQLite per test with FK enforcement ON.
- `client` (HTTP) and `db` (direct session) share the same engine so
  data written via HTTP is visible to a direct session and vice versa.
- Domain fixtures (sample_*) go through the service layer so audit
  logs are written, matching production behaviour.
"""

import os

os.environ["DB_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-not-for-production"
os.environ["DEBUG"] = "false"
os.environ["BUSINESS_TIMEZONE"] = "Asia/Kolkata"

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

get_settings.cache_clear()

from app.database import Base, get_db
from app.models import (  # noqa: F401 — register all models with metadata
    Address,
    AuditLog,
    Customer,
    Invoice,
    NumberSequence,
    Order,
    OrderItem,
    Payment,
    Product,
)

# ---------------------------------------------------------------------------
# Engine + session
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared connection => one shared in-memory DB
    )

    @event.listens_for(eng, "connect")
    def _fk_pragma(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


# Alias for older tests that use `db_session`
@pytest.fixture()
def db_session(db):
    return db


# ---------------------------------------------------------------------------
# HTTP TestClient — overrides get_db to use the test session
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(engine):
    from fastapi.testclient import TestClient

    from app.main import app

    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def _override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Minimal domain fixtures (direct, no service) — for pure unit tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def customer(db):
    c = Customer(name="Anita Rao", phone="9876543210")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def product(db):
    p = Product(
        sku="CHOC-500",
        name="Chocolate Truffle 500g",
        base_price=Decimal("99.99"),
        gst_rate=Decimal("5.00"),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ---------------------------------------------------------------------------
# Full-service fixtures used by existing HTTP tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_customer(db):
    """
    Creates a customer via the service layer (so audit is logged) plus
    one default active address. Existing tests assert on the name
    'Test Customer' and phone containing '99999'.
    """
    from app.services.customer_service import add_address, create_customer

    c = create_customer(db, {
        "name": "Test Customer",
        "phone": "+91 99999 99999",
        "email": "test@example.com",
        "notes": "",
    })
    add_address(db, c.id, {
        "label": "Home",
        "line": "123 Test Street, Test City",
        "is_default": True,
        "is_active": True,
    })
    db.refresh(c)
    return c


@pytest.fixture()
def sample_product(db):
    """Creates a product via the service layer so audit is logged."""
    from app.services.product_service import create_product

    return create_product(db, {
        "sku": "SAMPLE-001",
        "name": "Sample Cake",
        "base_price": Decimal("500.00"),
        "gst_rate": Decimal("5.00"),
        "category": "Cake",
        "prep_time_hours": 4,
    })


@pytest.fixture()
def sample_order(db, sample_customer, sample_product):
    from datetime import datetime, timedelta

    from app.services.order_service import create_order

    return create_order(db, {
        "customer_id": sample_customer.id,
        "items": [{"product_id": sample_product.id, "quantity": 1}],
        "delivery_type": "DELIVERY",
        "delivery_address": "123 Test Street, Test City",
        "fulfillment_date": (datetime.now() + timedelta(days=1)).isoformat(),
    })
