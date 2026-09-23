"""
Audit service — records every significant change to the database.

Python concept: This is a "fire and forget" pattern. After any mutation
(create/update/delete), the service is called with details of what changed.
It inserts a row into the audit_log table. The log is APPEND-ONLY —
no updates, no deletes. This gives you a tamper-evident trail.
"""

from datetime import datetime
from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(
    db: Session,
    entity_type: str,
    entity_id: int,
    action: str,
    old_value: dict | None = None,
    new_value: dict | None = None,
    changed_by: str = "system",
):
    """
    Record an audit log entry.

    Args:
        entity_type: "Customer", "Product", "Order", "Payment", "Invoice"
        entity_id: The ID of the entity
        action: "CREATE", "UPDATE", "DELETE", "STATUS_CHANGE", "PAYMENT"
        old_value: Dict of old field values (for UPDATE)
        new_value: Dict of new field values (for CREATE/UPDATE)
        changed_by: Who made the change (always "system" for now)
    """
    import json

    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_value=json.dumps(old_value) if old_value else None,
        new_value=json.dumps(new_value) if new_value else None,
        changed_by=changed_by,
    )
    db.add(entry)
    db.commit()