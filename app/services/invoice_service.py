"""
Invoice service.

- Numbering via NumberSequence (no race).
- Snapshot written at creation time. Immutable thereafter.
- PDF and thermal render read ONLY from the snapshot, never from Order.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Invoice, Order
from app.services.numbering import next_invoice_number
from app.utils import escpos_printer
from app.utils.money import money, split_gst

settings = get_settings()


def _pdf_dir() -> Path:
    d = Path("data") / "invoices"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_invoice(db: Session, order_id: int) -> Invoice:
    existing = db.execute(
        select(Invoice).where(Invoice.order_id == order_id)
    ).scalar_one_or_none()
    if existing:
        return existing

    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if not order.items:
        raise HTTPException(status_code=400, detail="Cannot invoice an order with no items")

    for attempt in range(2):
        try:
            invoice = _build_invoice(db, order)
            db.commit()
            db.refresh(invoice)
            return invoice
        except IntegrityError as exc:
            db.rollback()
            if attempt == 1:
                raise HTTPException(
                    status_code=409,
                    detail="Invoice number conflict, please retry",
                ) from exc

    raise HTTPException(status_code=500, detail="Unreachable")


def _build_invoice(db: Session, order: Order) -> Invoice:
    customer = order.customer
    default_addr = next(
        (a for a in customer.addresses if a.is_default and a.is_active),
        None,
    )

    items_snapshot = []
    gst_total = Decimal("0.00")
    subtotal = Decimal("0.00")
    for item in order.items:
        gst_total += money(item.gst_amount)
        subtotal += money(item.unit_price * Decimal(item.quantity))
        items_snapshot.append({
            "product_name": item.product.name,
            "sku": item.product.sku,
            "quantity": item.quantity,
            "unit_price": str(item.unit_price),
            "gst_rate": str(item.gst_rate),
            "gst_amount": str(item.gst_amount),
            "line_total": str(item.line_total),
            "customization_notes": item.customization_notes or "",
        })

    invoice = Invoice(
        order_id=order.id,
        invoice_number=next_invoice_number(db),
        status="ISSUED",

        business_name=settings.app_name,
        business_address=settings.address,
        business_phone=settings.phone,
        business_email=settings.email,
        business_gstin=settings.gstin,
        business_fssai=settings.fssai_number,

        billed_to_name=customer.name,
        billed_to_phone=customer.phone,
        billed_to_email=customer.email or "",
        billed_to_address=default_addr.line if default_addr else "",

        order_number=order.order_number,
        order_date=order.order_date,
        fulfillment_date=order.fulfillment_date,
        delivery_type=order.delivery_type,
        delivery_address=order.delivery_address or "",

        subtotal=money(subtotal),
        gst_total=money(gst_total),
        total_amount=money(order.total_amount),
        advance_paid=money(order.advance_paid),
        balance_due=money(order.balance_due),

        line_items_json=json.dumps(items_snapshot),
    )
    db.add(invoice)
    db.flush()
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


def _currency(amount: Decimal, symbol: str | None = None) -> str:
    sym = symbol if symbol is not None else settings.currency
    return f"{sym}{money(amount):.2f}"


def generate_pdf(db: Session, order_id: int) -> str:
    """Generate the invoice PDF from the SNAPSHOT."""
    invoice = get_invoice_for_order(db, order_id) or create_invoice(db, order_id)

    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.add_page()

    font_dir = Path(__file__).parent.parent / "static" / "fonts"
    use_unicode = (font_dir / "NotoSans-Regular.ttf").exists()
    if use_unicode:
        pdf.add_font("Noto", "", str(font_dir / "NotoSans-Regular.ttf"))
        pdf.add_font("Noto", "B", str(font_dir / "NotoSans-Bold.ttf"))
        font = "Noto"
        sym = settings.currency
    else:
        font = "Helvetica"
        sym = "Rs. "

    # --- Header ---
    pdf.set_font(font, "B", 16)
    pdf.cell(0, 10, invoice.business_name, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font(font, "", 9)
    for line in (
        invoice.business_address,
        invoice.business_phone,
        f"FSSAI: {invoice.business_fssai}" if invoice.business_fssai else "",
        f"GSTIN: {invoice.business_gstin}" if invoice.business_gstin else "",
    ):
        if line:
            pdf.cell(0, 5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    pdf.ln(4)
    pdf.set_font(font, "B", 12)
    pdf.cell(0, 7, "TAX INVOICE", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(font, "", 10)
    pdf.cell(0, 5, f"Invoice #: {invoice.invoice_number}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5, f"Date: {invoice.invoice_date.strftime('%d %b %Y')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5, f"Order #: {invoice.order_number}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # --- Bill To ---
    pdf.set_font(font, "B", 10)
    pdf.cell(0, 5, "BILL TO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(font, "", 10)
    pdf.cell(0, 5, invoice.billed_to_name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5, invoice.billed_to_phone, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if invoice.billed_to_email:
        pdf.cell(0, 5, invoice.billed_to_email, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if invoice.billed_to_address:
        pdf.cell(0, 5, invoice.billed_to_address, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # --- Fulfillment ---
    pdf.set_font(font, "B", 10)
    if invoice.delivery_type == "DELIVERY" and invoice.delivery_address:
        pdf.cell(0, 5, "DELIVER TO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font(font, "", 10)
        pdf.cell(0, 5, invoice.delivery_address, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        pdf.cell(0, 5, "PICKUP", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if invoice.fulfillment_date:
        pdf.set_font(font, "", 10)
        pdf.cell(0, 5, f"Ready by: {invoice.fulfillment_date.strftime('%d %b %Y, %H:%M')}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # --- Items (no HSN column) ---
    items = json.loads(invoice.line_items_json)
    show_gst = bool(invoice.business_gstin)

    pdf.set_font(font, "B", 9)
    pdf.cell(8, 7, "#", border=1, align="C")
    pdf.cell(80, 7, "Item", border=1)
    pdf.cell(12, 7, "Qty", border=1, align="R")
    pdf.cell(26, 7, "Rate", border=1, align="R")
    if show_gst:
        pdf.cell(22, 7, "GST", border=1, align="R")
    pdf.cell(26, 7, "Amount", border=1, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font(font, "", 9)
    for i, it in enumerate(items, 1):
        name = it["product_name"]
        if len(name) > 45:
            name = name[:42] + "..."
        pdf.cell(8, 6, str(i), border=1, align="C")
        pdf.cell(80, 6, name, border=1)
        pdf.cell(12, 6, str(it["quantity"]), border=1, align="R")
        pdf.cell(26, 6, _currency(Decimal(it["unit_price"]), sym), border=1, align="R")
        if show_gst:
            pdf.cell(22, 6, _currency(Decimal(it["gst_amount"]), sym), border=1, align="R")
        pdf.cell(26, 6, _currency(Decimal(it["line_total"]), sym), border=1, align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if it.get("customization_notes"):
            pdf.cell(8, 5, "")
            pdf.cell(0, 5, f"  Note: {it['customization_notes']}",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(5)

    # --- Totals ---
    pdf.set_font(font, "", 10)
    pdf.cell(130, 6, "")
    pdf.cell(35, 6, "Subtotal:", align="R")
    pdf.cell(35, 6, _currency(invoice.subtotal, sym), align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if invoice.business_gstin and invoice.gst_total > 0:
        cgst, sgst = split_gst(invoice.gst_total)
        pdf.cell(165, 6, "CGST:", align="R")
        pdf.cell(35, 6, _currency(cgst, sym), align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(165, 6, "SGST:", align="R")
        pdf.cell(35, 6, _currency(sgst, sym), align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font(font, "B", 11)
    pdf.cell(165, 7, "TOTAL:", align="R")
    pdf.cell(35, 7, _currency(invoice.total_amount, sym), align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font(font, "", 10)
    pdf.cell(165, 6, "Paid:", align="R")
    pdf.cell(35, 6, _currency(invoice.advance_paid, sym), align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if invoice.balance_due > 0:
        pdf.set_font(font, "B", 10)
        pdf.cell(165, 6, "Balance Due:", align="R")
        pdf.cell(35, 6, _currency(invoice.balance_due, sym), align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        pdf.cell(165, 6, "Status:", align="R")
        pdf.set_font(font, "B", 10)
        pdf.cell(35, 6, "PAID IN FULL", align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(10)
    pdf.set_font(font, "", 8)
    pdf.cell(0, 5, "This is a computer-generated invoice. No signature required.",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    if invoice.business_phone:
        pdf.cell(0, 5, f"For queries: {invoice.business_phone} | {invoice.business_name}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    out_path = _pdf_dir() / f"{invoice.invoice_number}.pdf"
    pdf.output(str(out_path))

    invoice.pdf_path = str(out_path)
    db.commit()
    return str(out_path)


def print_thermal_receipt(db: Session, order_id: int) -> None:
    """Print a receipt from the invoice snapshot."""
    invoice = get_invoice_for_order(db, order_id) or create_invoice(db, order_id)
    items = json.loads(invoice.line_items_json)
    escpos_printer.print_receipt_snapshot(invoice=invoice, items=items)
