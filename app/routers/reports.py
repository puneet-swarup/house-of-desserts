"""Reports page — list existing reports, generate new ones."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services import reports_service

router = APIRouter()


@router.get("", response_class=HTMLResponse)
def reports_page(
    request: Request,
    generated: str = Query("", description="Set after a successful generation"),
    error: str = Query("", description="Set if generation failed"),
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates
    settings = request.app.state.settings

    existing = reports_service.list_existing_reports()
    now = datetime.now()

    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context={
            "settings": settings,
            "reports": existing,
            "now_year": now.year,
            "now_month": now.month,
            "generated": generated,
            "error": error,
            "month_names": reports_service.MONTH_NAMES,
        },
    )


@router.post("/generate", response_class=HTMLResponse)
def generate(
    year: int = Form(..., ge=2000, le=2100),
    month: int = Form(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    try:
        result = reports_service.generate_report(db, year, month)
    except Exception as exc:
        return RedirectResponse(
            url=f"/reports?error={exc}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/reports?generated={result['year']}-{result['month']:02d}",
        status_code=303,
    )


@router.get("/download/{filename}")
def download(filename: str):
    """
    Serve a previously generated report.
    Filename format: YYYY-MM.pdf or YYYY-MM.csv — validated to prevent
    path traversal.
    """
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    parts = filename.split(".")
    if len(parts) != 2 or parts[1] not in ("pdf", "csv"):
        raise HTTPException(status_code=400, detail="Invalid filename")

    stem_parts = parts[0].split("-")
    if len(stem_parts) != 2 or not stem_parts[0].isdigit() or not stem_parts[1].isdigit():
        raise HTTPException(status_code=400, detail="Invalid filename")

    settings = get_settings()
    path = Path(settings.reports_dir) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    media = "application/pdf" if parts[1] == "pdf" else "text/csv"
    return FileResponse(path=str(path), media_type=media, filename=filename)
