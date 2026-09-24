"""Audit log — append-only record of all significant changes."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.time import utcnow


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)

    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    changed_by: Mapped[str] = mapped_column(
        String(50), nullable=False, default="system"
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_changed_at", "changed_at"),
        Index("ix_audit_log_action", "action"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} {self.entity_type}#{self.entity_id} "
            f"{self.action} at {self.changed_at}>"
        )
