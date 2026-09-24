"""Today page — dispatch list and production needs."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import today_service

router = APIRouter()


@router.get("/today", response_class=HTMLResponse)
def today_page(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings

    dispatch = today_service.dispatch_today(db)
    production = today_service.production_this_week(db)

    return templates.TemplateResponse(
        request=request,
        name="today.html",
        context={
            "settings": settings,
            "dispatch": dispatch,
            "production": production,
        },
    )
