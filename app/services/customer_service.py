from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, Address
from app.services.audit_service import log_action


def get_customer(db: Session, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def list_customers(db: Session, include_inactive: bool = False) -> list[Customer]:
    query = select(Customer).order_by(Customer.name)
    if not include_inactive:
        query = query.where(Customer.is_active == True)
    return list(db.execute(query).scalars().all())


def create_customer(db: Session, data: dict) -> Customer:
    existing = db.execute(
        select(Customer).where(Customer.phone == data["phone"], Customer.is_active == True)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"Phone '{data['phone']}' already registered")
    customer = Customer(**data)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    log_action(db, entity_type="Customer", entity_id=customer.id, action="CREATE",
               new_value={"name": data["name"], "phone": data["phone"]})
    return customer


def update_customer(db: Session, customer_id: int, data: dict) -> Customer:
    customer = get_customer(db, customer_id)
    if "phone" in data and data["phone"] != customer.phone:
        existing = db.execute(
            select(Customer).where(Customer.phone == data["phone"], Customer.is_active == True)
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail=f"Phone '{data['phone']}' already registered")
    for key, value in data.items():
        if value is not None:
            setattr(customer, key, value)
    db.commit()
    db.refresh(customer)
    return customer


def soft_delete_customer(db: Session, customer_id: int) -> Customer:
    """Soft delete customer + cascade soft delete their addresses."""
    customer = get_customer(db, customer_id)
    customer.is_active = False

    # Cascade: soft delete all active addresses
    for addr in customer.addresses:
        if addr.is_active:
            addr.is_active = False

    db.commit()
    db.refresh(customer)
    log_action(db, entity_type="Customer", entity_id=customer_id, action="DELETE",
               old_value={"name": customer.name, "phone": customer.phone})
    return customer