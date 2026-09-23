from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.audit_service import log_action
from app.config import get_settings
from app.models import Order, OrderItem, OrderStatus, Payment, Product

settings = get_settings()


def _generate_order_number(db: Session) -> str:
    year = datetime.now().year
    prefix = f"{settings.invoice_prefix}-{year}-"
    count = db.execute(select(Order).where(Order.order_number.like(f"{prefix}%"))).scalars().all()
    seq = len(count) + 1
    return f"{prefix}{seq:04d}"


def list_orders(db: Session, status: str = "ALL") -> list[Order]:
    query = select(Order).order_by(Order.created_at.desc())
    if status != "ALL":
        query = query.where(Order.status == OrderStatus(status))
    return list(db.execute(query).scalars().all())


def get_order(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def create_order(db: Session, data: dict) -> Order:
    """
    data keys:
        customer_id, delivery_type, delivery_date, delivery_address, notes,
        items: list of {product_id, quantity, customization_notes},
        advance_paid, advance_method
    """
    order = Order(
        order_number=_generate_order_number(db),
        customer_id=data["customer_id"],
        status=OrderStatus.CONFIRMED,
        order_date=datetime.fromisoformat(data["order_date"]) if data.get("order_date") else datetime.now(),
        delivery_type=data.get("delivery_type", "PICKUP"),
        delivery_date=data.get("delivery_date"),
        delivery_address=data.get("delivery_address"),
        notes=data.get("notes"),
    )
    db.add(order)
    db.flush()  # Get the order ID

    # Add items
    total = 0.0
    for item_data in data["items"]:
        product = db.get(Product, item_data["product_id"])
        if not product:
            raise HTTPException(status_code=400, detail="Invalid product ID")
        qty = item_data["quantity"]
        unit_price = product.base_price
        gst_amount = round(unit_price * qty * product.gst_rate / 100, 2)
        line_total = round(unit_price * qty + gst_amount, 2)
        total += line_total

        item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=qty,
            unit_price=unit_price,
            gst_amount=gst_amount,
            line_total=line_total,
            customization_notes=item_data.get("customization_notes"),
        )
        db.add(item)

    # Set totals
    advance = data.get("advance_paid", 0.0)
    order.total_amount = round(total, 2)
    order.advance_paid = advance
    order.balance_due = round(total - advance, 2)

    # Record advance as a payment if > 0
    if advance > 0:
        payment = Payment(
            order_id=order.id,
            amount=advance,
            method=data.get("advance_method", "UPI"),
        )
        db.add(payment)

    db.commit()
    db.refresh(order)
    log_action(
        db, entity_type="Order", entity_id=order.id, action="CREATE",
        new_value={"order_number": order.order_number, "customer_id": data["customer_id"], "total": order.total_amount},
    )
    return order


def update_status(db: Session, order_id: int, new_status: str) -> Order:
    order = get_order(db, order_id)
    old_status = order.status.value
    order.status = OrderStatus(new_status)
    db.commit()
    db.refresh(order)
    log_action(
        db, entity_type="Order", entity_id=order.id, action="STATUS_CHANGE",
        old_value={"status": old_status},
        new_value={"status": new_status},
    )
    return order


def record_payment(db: Session, order_id: int, amount: float, method: str, reference: str | None) -> Order:
    order = get_order(db, order_id)
    payment = Payment(
        order_id=order.id,
        amount=amount,
        method=method,
        reference=reference,
    )
    db.add(payment)
    order.advance_paid = round(order.advance_paid + amount, 2)
    order.balance_due = round(order.total_amount - order.advance_paid, 2)
    if order.balance_due <= 0:
        order.balance_due = 0
        order.status = OrderStatus.PAID
    db.commit()
    db.refresh(order)
    log_action(
        db, entity_type="Payment", entity_id=payment.id, action="PAYMENT",
        new_value={"order_id": order_id, "amount": amount, "method": method, "reference": reference},
    )
    return order   