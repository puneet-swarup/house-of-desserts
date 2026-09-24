"""
Audit service.

Contract: log_action() NEVER commits. It adds a row to the session.
The caller is responsible for a single db.commit() that persists both
the mutation and the audit entry atomically.

If an audit write fails, the whole transaction rolls back — which is
what you want for financial records.
"""

from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def _json_default(obj):
    """Serialize Decimal, datetime, and Enum to plain values."""
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "value"):  # Enum
        return obj.value
    return str(obj)


def log_action(
    db: Session,
    entity_type: str,
    entity_id: int,
    action: str,
    old_value: dict | None = None,
    new_value: dict | None = None,
    changed_by: str = "system",
) -> AuditLog:
    """
    Add an audit entry to the session. Does NOT commit.

    Caller must db.commit() to persist. If the caller's transaction
    rolls back, this entry is discarded too.
    """
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_value=json.dumps(old_value, default=_json_default) if old_value else None,
        new_value=json.dumps(new_value, default=_json_default) if new_value else None,
        changed_by=changed_by,
    )
    db.add(entry)
    return entry
