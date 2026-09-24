"""
Model package. Import order matters: Base first, then concrete models,
then any that reference each other via string relationships.
"""

from app.database import Base
from app.models.address import Address
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.number_sequence import NumberSequence
from app.models.order import ALLOWED_TRANSITIONS, Order, OrderItem, OrderStatus
from app.models.payment import Payment
from app.models.product import Product

__all__ = [
    "Base",
    "AuditLog",
    "NumberSequence",
    "Customer",
    "Address",
    "Product",
    "Order",
    "OrderItem",
    "OrderStatus",
    "ALLOWED_TRANSITIONS",
    "Payment",
    "Invoice",
]
