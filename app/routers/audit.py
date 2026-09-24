"""Audit log page — append-only view of all changes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog

router = APIRouter()


@router.get("", response_class=HTMLResponse)
def audit_page(request: Request, entity: str = "ALL", db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings

    query = select(AuditLog).order_by(AuditLog.changed_at.desc()).limit(200)
    if entity != "ALL":
        query = query.where(AuditLog.entity_type == entity)

    logs = list(db.execute(query).scalars().all())

    return templates.TemplateResponse(
        request=request,
        name="audit.html",
        context={"settings": settings, "logs": logs, "filter": entity},
    )
