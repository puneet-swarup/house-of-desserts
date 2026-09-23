"""
Invoice service — handles invoice numbering, PDF generation, and thermal printing.
"""

from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Invoice, Order, OrderItem, Payment
from app.utils import escpos_printer
from pathlib import Path

settings = get_settings()

# PDF output directory
PDF_DIR = Path("data") / "invoices"
PDF_DIR.mkdir(parents=True, exist_ok=True)

def _currency(amount: float) -> str:
    """Format currency for PDF (Helvetica doesn't support ₹)."""
    return f"Rs. {amount:.2f}"

def _next_invoice_number(db: Session) -> str:
    """Generate the next sequential invoice number: HOD-2026-0001, HOD-2026-0002, ..."""
    year = datetime.now().year
    prefix = f"{settings.invoice_prefix}-{year}-"
    count = db.execute(
        select(Invoice).where(Invoice.invoice_number.like(f"{prefix}%"))
    ).scalars().all()
    seq = len(count) + 1
    return f"{prefix}{seq:04d}"


def create_invoice(db: Session, order_id: int) -> Invoice:
    """Create (or return existing) invoice for an order."""
    existing = db.execute(
        select(Invoice).where(Invoice.order_id == order_id)
    ).scalar_one_or_none()
    if existing:
        return existing

    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    invoice = Invoice(
        order_id=order.id,
        invoice_number=_next_invoice_number(db),
        status="ISSUED",
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def get_invoice(db: Session, invoice_id: int) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


def get_invoice_for_order(db: Session, order_id: int) -> Invoice | None:
    return db.execute(
        select(Invoice).where(Invoice.order_id == order_id)
    ).scalar_one_or_none()


def print_thermal_receipt(db: Session, order_id: int):
    """Trigger thermal printer for the given order."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    customer = order.customer
    items = order.items
    gst_total = sum(item.gst_amount for item in items)

    invoice = get_invoice_for_order(db, order_id) or create_invoice(db, order_id)

    escpos_printer.print_receipt(
        order=order,
        customer=customer,
        items=items,
        total=order.total_amount,
        gst_total=gst_total,
        advance=order.advance_paid,
        balance=order.balance_due,
        invoice_number=invoice.invoice_number,
        delivery_type=order.delivery_type,
        delivery_address=order.delivery_address or "",
    )


def generate_pdf(db: Session, order_id: int) -> str:
    """
    Generate a PDF invoice using fpdf2.
    Returns the file path to the generated PDF.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    invoice = get_invoice_for_order(db, order_id) or create_invoice(db, order_id)
    customer = order.customer
    items = order.items
    gst_total = sum(item.gst_amount for item in items)
    subtotal = order.total_amount - gst_total

    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.add_page()

    _font_dir = Path(__file__).parent.parent / "static" / "fonts"
    if (_font_dir / "NotoSans-Regular.ttf").exists():
        pdf.add_font("Noto", "", str(_font_dir / "NotoSans-Regular.ttf"))
        pdf.add_font("Noto", "B", str(_font_dir / "NotoSans-Bold.ttf"))
        _font = "Noto"
    else:
        _font = "Helvetica"

    # === HEADER ===
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, settings.app_name, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "", 9)
    if settings.address:
        pdf.cell(0, 5, settings.address, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    if settings.phone:
        pdf.cell(0, 5, settings.phone, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    if settings.fssai_number:
        pdf.cell(0, 5, f"FSSAI: {settings.fssai_number}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    if settings.gstin:
        pdf.cell(0, 5, f"GSTIN: {settings.gstin}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    pdf.ln(4)

    # === INVOICE META ===
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "TAX INVOICE", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Invoice #: {invoice.invoice_number}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5, f"Date: {order.order_date.strftime('%d %b %Y')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5, f"Order #: {order.order_number}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # === BILL TO ===
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, "BILL TO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, customer.name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5, customer.phone, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if customer.email:
        pdf.cell(0, 5, customer.email, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    # Default address
    default_addr = next(
        (a for a in customer.addresses if a.is_default and a.is_active), None
    )
    if default_addr:
        pdf.cell(0, 5, default_addr.line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # === DELIVERY ===
    if order.delivery_type == "DELIVERY" and order.delivery_address:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 5, "DELIVER TO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 5, order.delivery_address, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if order.delivery_date:
            pdf.cell(0, 5, f"Delivery Date: {order.delivery_date.strftime('%d %b %Y')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)
    else:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 5, "PICKUP", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        if order.delivery_date:
            pdf.cell(0, 5, f"Ready: {order.delivery_date.strftime('%d %b %Y')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

    # === ITEMS TABLE ===
    show_gst_col = bool(settings.gstin)

    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(8, 7, "#", border=1, align="C")
    pdf.cell(62, 7, "Item", border=1)
    pdf.cell(14, 7, "HSN", border=1, align="C")
    pdf.cell(12, 7, "Qty", border=1, align="R")
    pdf.cell(22, 7, "Rate", border=1, align="R")
    if show_gst_col:
        pdf.cell(22, 7, "GST", border=1, align="R")
    pdf.cell(24, 7, "Amount", border=1, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 9)
    for i, item in enumerate(items, 1):
        name = item.product.name[:40]
        if len(item.product.name) > 40:
            name = name[:37] + "..."

        pdf.cell(8, 6, str(i), border=1, align="C")
        pdf.cell(62, 6, name, border=1)
        pdf.cell(14, 6, item.product.hsn_code, border=1, align="C")
        pdf.cell(12, 6, str(item.quantity), border=1, align="R")
        pdf.cell(22, 6, f"{item.unit_price:.2f}", border=1, align="R")
        if show_gst_col:
            pdf.cell(22, 6, f"{item.gst_amount:.2f}", border=1, align="R")
        pdf.cell(24, 6, f"{item.line_total:.2f}", border=1, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if item.customization_notes:
            pdf.cell(8, 5, "")
            pdf.cell(0, 5, f"  Note: {item.customization_notes}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(5)

    # === TOTALS ===
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(120, 6, "")
    pdf.cell(35, 6, "Subtotal:", align="R")
    pdf.cell(35, 6, f"{subtotal:.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if settings.gstin and gst_total > 0:
        # Derive rate from the first item's product (all same rate for home bakery)
        gst_rate = items[0].product.gst_rate if items else 0
        half_rate = gst_rate / 2
        cgst = gst_total / 2
        sgst = gst_total / 2
        pdf.cell(35, 6, f"CGST @ {half_rate}:%", align="R")
        pdf.cell(35, 6, f"{cgst:.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(35, 6, f"SGST @ {half_rate}:%", align="R")
        pdf.cell(35, 6, f"{sgst:.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        # Not registered: no GST lines at all

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(35, 7, "TOTAL:", align="R")
    pdf.cell(35, 7, f"{order.total_amount:.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(35, 6, "Paid:", align="R")
    pdf.cell(35, 6, f"{order.advance_paid:.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if order.balance_due > 0:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(35, 6, "Balance Due:", align="R")
        pdf.cell(35, 6, f"{order.balance_due:.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        pdf.cell(35, 6, "Status:", align="R")
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(35, 6, "PAID IN FULL", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # === FOOTER ===
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 5, "This is a computer-generated invoice. No signature required.", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    if settings.phone:
        pdf.cell(0, 5, f"For queries: {settings.phone} | {settings.app_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    # === SAVE ===
    pdf_filename = f"{invoice.invoice_number}.pdf"
    pdf_path = PDF_DIR / pdf_filename
    pdf.output(str(pdf_path))

    invoice.pdf_path = str(pdf_path)
    db.commit()

    return str(pdf_path)   