"""
Audit log — append-only record of all significant changes.
No updates, no deletes. This is your financial transparency trail.
"""

from datetime import datetime

from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # What was changed: "Customer", "Order", "Product", "Payment", "Invoice"
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=False)

    # What happened: "CREATE", "UPDATE", "DELETE", "STATUS_CHANGE", "PAYMENT"
    action: Mapped[str] = mapped_column(String(20), nullable=False)

    # What changed (JSON string for flexibility)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Who/what made the change
    changed_by: Mapped[str] = mapped_column(String(50), nullable=False, default="system")

    changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} {self.entity_type}#{self.entity_id} "
            f"{self.action} at {self.changed_at}>"
        )   