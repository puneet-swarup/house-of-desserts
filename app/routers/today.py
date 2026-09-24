"""Today page — dispatch list and production needs."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import today_service
from app.services.whatsapp_service import messages_for_order

router = APIRouter()


@router.get("/today", response_class=HTMLResponse)
def today_page(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings

    dispatch = today_service.dispatch_today(db)
    production = today_service.production_this_week(db)

    # Attach a single quick-action WhatsApp link per order.
    # Pick "ready" as the default message — the most common one-tap action.
    for order in dispatch:
        messages = messages_for_order(order)
        ready = next((m for m in messages if m["key"] == "ready"), None)
        order.wa_ready = ready  # type: ignore[attr-defined]

    return templates.TemplateResponse(
        request=request,
        name="today.html",
        context={
            "settings": settings,
            "dispatch": dispatch,
            "production": production,
        },
    )
