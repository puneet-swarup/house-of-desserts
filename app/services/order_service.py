"""
Order business logic.

Key guarantees:
- Single commit per public function.
- Audit entry written in the same transaction.
- Money computed with Decimal, rounded per-line, half-up.
- Status changes validated against ALLOWED_TRANSITIONS.
- Order number from NumberSequence, unique-constrained.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Customer,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    Product,
)
from app.services.audit_service import log_action
from app.services.numbering import next_order_number
from app.utils.money import gst_for_line, line_total_with_gst, money
from app.utils.time import utcnow

settings = get_settings()


# --- Reads ---

def list_orders(db: Session, status: str = "ALL") -> list[Order]:
    """
    Sort:
      1. fulfillment_date ASC, NULLs last (nearest fulfillment on top)
      2. order_date DESC (most recently placed first, as a tiebreaker)
    """
    from sqlalchemy import nullslast

    query = (
        select(Order)
        .order_by(
            nullslast(Order.fulfillment_date.asc()),
            Order.order_date.desc(),
        )
    )
    if status != "ALL":
        try:
            status_enum = OrderStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from exc
        query = query.where(Order.status == status_enum)
    return list(db.execute(query).scalars().all())


def get_order(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


# --- Writes ---

def create_order(db: Session, data: dict) -> Order:
    """
    data keys:
        customer_id, delivery_type, fulfillment_date, delivery_address, notes,
        items: list of {product_id, quantity, customization_notes},
        advance_paid, advance_method, order_date
    """
    items_data = data.get("items") or []
    if not items_data:
        raise HTTPException(status_code=400, detail="An order must have at least one item")

    customer = db.get(Customer, data["customer_id"])
    if not customer or not customer.is_active:
        raise HTTPException(status_code=400, detail="Invalid or inactive customer")

    for attempt in range(2):
        try:
            order = _build_order(db, data, items_data)
            db.commit()
            db.refresh(order)
            return order
        except IntegrityError as exc:
            db.rollback()
            if attempt == 1:
                raise HTTPException(
                    status_code=409,
                    detail="Order number conflict, please retry",
                ) from exc

    raise HTTPException(status_code=500, detail="Unreachable")


def _build_order(db: Session, data: dict, items_data: list[dict]) -> Order:
    order_number = next_order_number(db)

    order = Order(
        order_number=order_number,
        customer_id=data["customer_id"],
        status=OrderStatus.CONFIRMED,
        order_date=_parse_dt(data.get("order_date")) or utcnow(),
        delivery_type=data.get("delivery_type", "PICKUP"),
        fulfillment_date=_parse_dt(data.get("fulfillment_date")),
        delivery_address=data.get("delivery_address") or None,
        notes=data.get("notes") or None,
    )
    db.add(order)
    db.flush()

    total = Decimal("0.00")
    for item_data in items_data:
        product = db.get(Product, item_data["product_id"])
        if not product or not product.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid or inactive product: {item_data['product_id']}",
            )
        qty = int(item_data["quantity"])
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be positive")

        unit_price = money(product.base_price)
        gst_rate = money(product.gst_rate)
        gst_amount = gst_for_line(unit_price, qty, gst_rate)
        line_total = line_total_with_gst(unit_price, qty, gst_amount)

        total += line_total

        db.add(OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=qty,
            unit_price=unit_price,
            gst_rate=gst_rate,
            gst_amount=gst_amount,
            line_total=line_total,
            customization_notes=item_data.get("customization_notes") or None,
        ))

    advance = money(data.get("advance_paid") or 0)
    if advance < 0:
        raise HTTPException(status_code=400, detail="Advance cannot be negative")
    if advance > total:
        raise HTTPException(status_code=400, detail="Advance cannot exceed order total")

    order.total_amount = money(total)
    order.advance_paid = advance
    order.balance_due = money(total - advance)

    if advance > 0:
        db.add(Payment(
            order_id=order.id,
            amount=advance,
            method=data.get("advance_method", "UPI"),
        ))

    log_action(
        db,
        entity_type="Order",
        entity_id=order.id,
        action="CREATE",
        new_value={
            "order_number": order.order_number,
            "customer_id": order.customer_id,
            "total_amount": order.total_amount,
            "advance_paid": order.advance_paid,
            "balance_due": order.balance_due,
            "items_count": len(items_data),
        },
    )
    return order


def update_status(db: Session, order_id: int, new_status: str) -> Order:
    order = get_order(db, order_id)
    try:
        target = OrderStatus(new_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}") from exc

    if target == order.status:
        return order

    if not order.can_transition_to(target):
        raise HTTPException(
            status_code=400,
            detail=f"Illegal transition: {order.status.value} -> {target.value}",
        )

    old_status = order.status.value
    order.status = target

    log_action(
        db,
        entity_type="Order",
        entity_id=order.id,
        action="STATUS_CHANGE",
        old_value={"status": old_status},
        new_value={"status": target.value},
    )
    db.commit()
    db.refresh(order)
    return order


def record_payment(
    db: Session,
    order_id: int,
    amount: Decimal | float,
    method: str,
    reference: str | None,
    received_at: datetime | None = None,
) -> Order:
    order = get_order(db, order_id)

    if order.status == OrderStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot record payment on a cancelled order")
    if order.status == OrderStatus.PAID:
        raise HTTPException(status_code=400, detail="Order is already fully paid")

    amt = money(amount)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")
    if amt > order.balance_due:
        raise HTTPException(
            status_code=400,
            detail=f"Payment exceeds balance due ({order.balance_due})",
        )

    payment = Payment(
        order_id=order.id,
        amount=amt,
        method=method,
        reference=reference or None,
        received_at=received_at or utcnow(),
    )
    db.add(payment)
    db.flush()

    order.advance_paid = money(order.advance_paid + amt)
    order.balance_due = money(order.total_amount - order.advance_paid)

    if order.balance_due <= Decimal("0.00"):
        order.balance_due = Decimal("0.00")
        if order.can_transition_to(OrderStatus.PAID):
            order.status = OrderStatus.PAID

    log_action(
        db,
        entity_type="Payment",
        entity_id=payment.id,
        action="PAYMENT",
        new_value={
            "order_id": order_id,
            "amount": amt,
            "method": method,
            "reference": reference,
            "balance_after": order.balance_due,
        },
    )
    db.commit()
    db.refresh(order)
    return order


# --- Helpers ---

def _parse_dt(value):
    """Accept datetime, ISO string, or None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
