"""Customer business logic."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Address, Customer
from app.services.audit_service import log_action

PAGE_SIZE_DEFAULT = 25
PAGE_SIZE_MAX = 100


def get_customer(db: Session, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def list_customers(db: Session, include_inactive: bool = False) -> list[Customer]:
    """Return all customers (unpaginated). Kept for existing callers."""
    query = select(Customer).order_by(Customer.name)
    if not include_inactive:
        query = query.where(Customer.is_active.is_(True))
    return list(db.execute(query).scalars().all())


def search_customers(
    db: Session,
    q: str | None = None,
    page: int = 1,
    per_page: int = PAGE_SIZE_DEFAULT,
    include_inactive: bool = False,
) -> tuple[list[Customer], dict]:
    """
    Paginated customer list with optional search across name and phone.

    Returns (customers, meta) where meta = {
        "q": str, "page": int, "per_page": int,
        "total": int, "pages": int,
        "has_prev": bool, "has_next": bool,
    }
    """
    page = max(1, page)
    per_page = max(1, min(per_page, PAGE_SIZE_MAX))

    base = select(Customer)
    count_q = select(func.count(Customer.id))

    conditions = []
    if not include_inactive:
        conditions.append(Customer.is_active.is_(True))

    if q:
        term = f"%{q.strip()}%"
        conditions.append(or_(Customer.name.ilike(term), Customer.phone.ilike(term)))

    if conditions:
        base = base.where(*conditions)
        count_q = count_q.where(*conditions)

    total = db.execute(count_q).scalar() or 0
    pages = (total + per_page - 1) // per_page if total else 1

    if page > pages:
        page = pages

    offset = (page - 1) * per_page
    rows = db.execute(base.order_by(Customer.name).limit(per_page).offset(offset)).scalars().all()

    meta = {
        "q": q or "",
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
    }
    return list(rows), meta


def create_customer(db: Session, data: dict) -> Customer:
    customer = Customer(**data)
    db.add(customer)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Phone '{data.get('phone')}' is already registered to an active customer",
        ) from exc

    log_action(
        db,
        entity_type="Customer",
        entity_id=customer.id,
        action="CREATE",
        new_value={"name": customer.name, "phone": customer.phone},
    )
    db.commit()
    db.refresh(customer)
    return customer


def update_customer(db: Session, customer_id: int, data: dict) -> Customer:
    customer = get_customer(db, customer_id)

    old = {k: getattr(customer, k) for k in data if hasattr(customer, k)}

    for key, value in data.items():
        setattr(customer, key, value)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Phone '{data.get('phone')}' is already registered to an active customer",
        ) from exc

    log_action(
        db,
        entity_type="Customer",
        entity_id=customer.id,
        action="UPDATE",
        old_value=old,
        new_value={k: getattr(customer, k) for k in data if hasattr(customer, k)},
    )
    db.commit()
    db.refresh(customer)
    return customer


def soft_delete_customer(db: Session, customer_id: int) -> Customer:
    customer = get_customer(db, customer_id)
    customer.is_active = False
    for addr in customer.addresses:
        if addr.is_active:
            addr.is_active = False

    log_action(
        db,
        entity_type="Customer",
        entity_id=customer.id,
        action="DELETE",
        old_value={"name": customer.name, "phone": customer.phone},
    )
    db.commit()
    db.refresh(customer)
    return customer


# --- Addresses ---


def add_address(db: Session, customer_id: int, data: dict) -> Address:
    """
    Add an address. Rules:
    - The first active address is ALWAYS marked default.
    - If the new address is marked default, demote the others.
    """
    customer = get_customer(db, customer_id)
    has_existing_active = any(a.is_active for a in customer.addresses)

    address = Address(customer_id=customer.id, **data)

    if not has_existing_active:
        address.is_default = True

    if address.is_default:
        for a in customer.addresses:
            if a.is_active and a.is_default:
                a.is_default = False

    db.add(address)
    db.flush()
    log_action(
        db,
        entity_type="Address",
        entity_id=address.id,
        action="CREATE",
        new_value={
            "customer_id": customer_id,
            "label": address.label,
            "is_default": address.is_default,
        },
    )
    db.commit()
    db.refresh(address)
    return address


def set_default_address(db: Session, customer_id: int, address_id: int) -> Address:
    """Mark an address as default; demote all others."""
    customer = get_customer(db, customer_id)
    target = None
    for a in customer.addresses:
        if a.id == address_id and a.is_active:
            target = a
            break
    if not target:
        raise HTTPException(status_code=404, detail="Address not found")

    for a in customer.addresses:
        a.is_default = a.id == address_id

    log_action(
        db,
        entity_type="Address",
        entity_id=address_id,
        action="SET_DEFAULT",
        new_value={"customer_id": customer_id},
    )
    db.commit()
    db.refresh(target)
    return target


def customer_stats(db: Session, customer_id: int) -> dict:
    """
    Aggregate statistics for one customer.

    Excludes CANCELLED orders from all money and count totals. Cancelled
    orders are counted separately as informational context.

    Returns a dict:
      {
        "order_count": int,
        "cancelled_count": int,
        "lifetime_value": Decimal,
        "collected": Decimal,
        "outstanding": Decimal,
        "average_order_value": Decimal,
        "first_order_date": datetime | None,
        "last_order_date": datetime | None,
      }
    """
    from decimal import Decimal

    from sqlalchemy import func

    from app.models import Order, OrderStatus

    # Non-cancelled aggregates
    active_row = db.execute(
        select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
            func.coalesce(func.sum(Order.advance_paid), 0),
            func.coalesce(func.sum(Order.balance_due), 0),
            func.min(Order.order_date),
            func.max(Order.order_date),
        ).where(
            Order.customer_id == customer_id,
            Order.status != OrderStatus.CANCELLED,
        )
    ).one()

    count, ltv, collected, outstanding, first_date, last_date = active_row
    count = int(count or 0)
    ltv_d = Decimal(str(ltv or 0)).quantize(Decimal("0.01"))
    collected_d = Decimal(str(collected or 0)).quantize(Decimal("0.01"))
    outstanding_d = Decimal(str(outstanding or 0)).quantize(Decimal("0.01"))
    avg = (ltv_d / count).quantize(Decimal("0.01")) if count > 0 else Decimal("0.00")

    cancelled = (
        db.execute(
            select(func.count(Order.id)).where(
                Order.customer_id == customer_id,
                Order.status == OrderStatus.CANCELLED,
            )
        ).scalar()
        or 0
    )

    return {
        "order_count": count,
        "cancelled_count": int(cancelled),
        "lifetime_value": ltv_d,
        "collected": collected_d,
        "outstanding": outstanding_d,
        "average_order_value": avg,
        "first_order_date": first_date,
        "last_order_date": last_date,
    }
