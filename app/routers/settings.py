"""Settings page — read-only view of .env configuration."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"settings": settings},
    )
