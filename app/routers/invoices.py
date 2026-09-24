"""
Invoice routes — preview, PDF download, thermal print.
"""

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order
from app.services import invoice_service

router = APIRouter()


def _deserialize_items(invoice) -> list[dict]:
    """Parse line_items_json back to typed dicts for template rendering."""
    raw = json.loads(invoice.line_items_json or "[]")
    out = []
    for r in raw:
        out.append({
            "product_name": r.get("product_name", ""),
            "sku": r.get("sku", ""),
            "quantity": r.get("quantity", 0),
            "unit_price": Decimal(r.get("unit_price", "0")),
            "gst_rate": Decimal(r.get("gst_rate", "0")),
            "gst_amount": Decimal(r.get("gst_amount", "0")),
            "line_total": Decimal(r.get("line_total", "0")),
            "customization_notes": r.get("customization_notes", ""),
        })
    return out


@router.post("/orders/{order_id}/print-receipt")
def print_receipt(order_id: int, db: Session = Depends(get_db)):
    invoice_service.print_thermal_receipt(db, order_id)
    return {"ok": True, "message": "Receipt sent to printer"}


@router.get("/orders/{order_id}/generate-pdf")
def generate_pdf(order_id: int, db: Session = Depends(get_db)):
    pdf_path = invoice_service.generate_pdf(db, order_id)
    filename = pdf_path.replace("\\", "/").split("/")[-1]
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.get("/orders/{order_id}/invoice")
def view_invoice(request: Request, order_id: int, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings

    order = db.get(Order, order_id)
    if not order:
        return RedirectResponse(url="/orders", status_code=303)

    invoice = invoice_service.get_invoice_for_order(db, order_id)
    if not invoice:
        invoice = invoice_service.create_invoice(db, order_id)

    items = _deserialize_items(invoice)

    return templates.TemplateResponse(
        request=request,
        name="invoices/preview.html",
        context={
            "settings": settings,
            "invoice": invoice,
            "items": items,
        },
    )
