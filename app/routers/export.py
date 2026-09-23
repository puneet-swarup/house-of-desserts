"""
Export routes — CSV/JSON downloads for tax filing.
"""

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import PlainTextResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import export_service

router = APIRouter()


@router.get("/export", response_class=HTMLResponse)
def export_page(request: Request):
    """Show the export form (date range picker + format selection)."""
    templates = request.app.state.templates
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="export.html",
        context={"settings": settings},
    )


@router.get("/export/orders.csv")
def export_orders(
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    filename, content = export_service.export_orders_csv(db, start, end)
    return PlainTextResponse(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/payments.csv")
def export_payments(
    start: str = Query(...),
    end: str = Query(...),
    db: Session = Depends(get_db),
):
    filename, content = export_service.export_payments_csv(db, start, end)
    return PlainTextResponse(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/summary.json")
def export_summary(
    start: str = Query(...),
    end: str = Query(...),
    db: Session = Depends(get_db),
):
    filename, content = export_service.export_summary_json(db, start, end)
    return PlainTextResponse(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )