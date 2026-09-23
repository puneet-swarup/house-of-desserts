"""
Invoice routes — print receipt, generate PDF, download.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import invoice_service
from app.models import Order

router = APIRouter()


@router.post("/orders/{order_id}/print-receipt")
def print_receipt(order_id: int, db: Session = Depends(get_db)):
    """Trigger thermal printer. Returns JSON confirmation."""
    invoice_service.print_thermal_receipt(db, order_id)
    return {"ok": True, "message": "Receipt sent to printer"}


@router.get("/orders/{order_id}/generate-pdf")
def generate_pdf(order_id: int, db: Session = Depends(get_db)):
    """Generate PDF and redirect to download."""
    pdf_path = invoice_service.generate_pdf(db, order_id)
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=pdf_path.split("/")[-1].split("\\")[-1],
    )


@router.get("/orders/{order_id}/invoice")
def view_invoice(request: Request, order_id: int, db: Session = Depends(get_db)):
    """Show on-screen invoice preview."""
    templates = request.app.state.templates
    settings = request.app.state.settings

    order = db.get(Order, order_id)
    if not order:
        return RedirectResponse(url="/orders", status_code=303)

    invoice = invoice_service.get_invoice_for_order(db, order_id)
    customer = order.customer
    items = order.items
    gst_total = sum(item.gst_amount for item in items)
    subtotal = order.total_amount - gst_total

    return templates.TemplateResponse(
        request=request,
        name="invoices/preview.html",
        context={
            "settings": settings,
            "order": order,
            "customer": customer,
            "items": items,
            "invoice": invoice,
            "gst_total": gst_total,
            "subtotal": subtotal,
        },
    )   