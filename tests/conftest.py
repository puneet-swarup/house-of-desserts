"""
Shared test fixtures.
Each test gets a FRESH in-memory SQLite database.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def client(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False)

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_customer(client, db_session):
    from app.models import Customer
    client.post("/customers", data={
        "name": "Test Customer",
        "phone": "+91 99999 99999",
        "email": "test@example.com",
        "notes": "",
        "addr_new_label": ["Home"],
        "addr_new_line": ["123 Test Street, Mumbai"],
        "addr_new_default": ["1"],
    })
    customer = db_session.query(Customer).filter_by(phone="+91 99999 99999").first()
    assert customer is not None, "Customer was not created"
    return customer


@pytest.fixture()
def sample_product(client, db_session):
    from app.models import Product
    client.post("/products", data={
        "name": "Choco Cake",
        "sku": "CHOC-001",
        "hsn_code": "1905",
        "category": "Cake",
        "base_price": "500.00",
        "gst_rate": "5.0",
        "prep_time_hours": "4",
        "description": "Test cake",
        "is_active": "1",
    })
    product = db_session.query(Product).filter_by(sku="CHOC-001").first()
    assert product is not None, "Product was not created"
    return product


@pytest.fixture()
def sample_order(client, db_session, sample_customer, sample_product):
    from app.models import Order
    client.post("/orders", data={
        "customer_id": str(sample_customer.id),
        "delivery_type": "DELIVERY",
        "delivery_date": "",
        "delivery_address": "123 Test Street, Mumbai",
        "notes": "Test order",
        "advance_paid": "200.00",
        "advance_method": "UPI",
        "product_id": [str(sample_product.id)],
        "quantity": ["2"],
    })
    order = db_session.query(Order).first()
    assert order is not None, "Order was not created"
    return order