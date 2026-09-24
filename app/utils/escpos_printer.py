"""
Thermal printer utility using python-escpos.

Two public functions:
- print_receipt(order, customer, items, ...)   — legacy, reads live order
- print_receipt_snapshot(invoice, items)       — new, reads from Invoice
                                                 snapshot (preferred)

PRINTER_TYPE options (from .env):
- "file"    -> Writes to data/receipt_preview.bin (for testing without a printer)
- "usb"     -> USB-connected printer
- "network" -> LAN/TCP printer
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.config import get_settings

settings = get_settings()


def get_printer():
    """Return a configured escpos printer instance."""
    from escpos.printer import File, Network, Usb

    if settings.printer_type == "file":
        output_path = Path("data") / "receipt_preview.bin"
        output_path.parent.mkdir(exist_ok=True)
        return File(str(output_path))

    elif settings.printer_type == "usb":
        # python-escpos Usb signature: Usb(idVendor, idProduct, ...)
        # PRINTER_DEVICE format: "vendor_id:product_id" in hex,
        # e.g. "0x0416:0x5011". Fall back to a known Epson profile.
        if ":" in settings.printer_device:
            vendor, prod = settings.printer_device.split(":", 1)
            vid = int(vendor, 0)
            pid = int(prod, 0)
            return Usb(vid, pid)
        # Default profile: Epson TM-T88III
        return Usb(0x04B8, 0x0005)

    elif settings.printer_type == "network":
        parts = settings.printer_device.split(":")
        ip = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 9100
        return Network(host=ip, port=port)

    else:
        raise ValueError(f"Unknown printer_type: {settings.printer_type!r}")


def _line_width() -> int:
    # 58mm -> 32 chars; 80mm -> 48 chars (standard for 203dpi thermal)
    return 32 if settings.printer_width == 58 else 48


def print_receipt_snapshot(invoice, items: list[dict]) -> None:
    """
    Print a receipt from an Invoice snapshot. `items` is a list of dicts
    deserialized from invoice.line_items_json. Never reads Order/Customer.
    """
    printer = get_printer()
    width = _line_width()

    printer.set(align="center", bold=True)
    printer.text(invoice.business_name.upper() + "\n")
    printer.set(bold=False)

    if invoice.business_address:
        printer.text(invoice.business_address + "\n")
    if invoice.business_phone:
        printer.text(invoice.business_phone + "\n")
    if invoice.business_fssai:
        printer.text(f"FSSAI: {invoice.business_fssai}\n")
    if invoice.business_gstin:
        printer.text(f"GSTIN: {invoice.business_gstin}\n")

    printer.set(align="left")
    printer.text("-" * width + "\n")

    printer.text(f"INV: {invoice.invoice_number}\n")
    printer.text(f"Date: {invoice.invoice_date.strftime('%d-%m-%Y %H:%M')}\n")
    printer.text(f"Customer: {invoice.billed_to_name}\n")
    printer.text(f"Phone: {invoice.billed_to_phone}\n")

    if invoice.delivery_type == "DELIVERY" and invoice.delivery_address:
        printer.text(f"Deliver To: {invoice.delivery_address}\n")
    else:
        printer.text("Type: PICKUP\n")

    printer.text("-" * width + "\n")

    printer.set(bold=True)
    if width >= 48:
        printer.text(f"{'Item':<28}{'Qty':>4}{'Rate':>8}{'Amt':>8}\n")
    else:
        printer.text(f"{'Item':<20}{'Qty':>3}{'Amt':>9}\n")
    printer.set(bold=False)

    for it in items:
        name = it["product_name"]
        max_name = 28 if width >= 48 else 20
        if len(name) > max_name:
            name = name[: max_name - 1] + "."

        qty = it["quantity"]
        unit = Decimal(it["unit_price"])
        line = Decimal(it["line_total"])

        if width >= 48:
            printer.text(f"{name:<28}{qty:>4}{unit:>8.2f}{line:>8.2f}\n")
        else:
            printer.text(f"{name:<20}{qty:>3}{line:>9.2f}\n")

        if it.get("customization_notes"):
            printer.text(f"  Note: {it['customization_notes']}\n")

    printer.text("-" * width + "\n")
    printer.text(f"Subtotal:{invoice.subtotal:>22.2f}\n")

    if invoice.business_gstin and invoice.gst_total > 0:
        half = (invoice.gst_total / Decimal("2")).quantize(Decimal("0.01"))
        other = invoice.gst_total - half
        printer.text(f"CGST:{half:>26.2f}\n")
        printer.text(f"SGST:{other:>26.2f}\n")

    printer.set(bold=True)
    printer.text(f"TOTAL:{invoice.total_amount:>23.2f}\n")
    printer.set(bold=False)
    printer.text(f"Paid:{invoice.advance_paid:>24.2f}\n")

    if invoice.balance_due > 0:
        printer.set(bold=True)
        printer.text(f"Balance Due:{invoice.balance_due:>17.2f}\n")
        printer.set(bold=False)
    else:
        printer.text(f"Balance Due:{'PAID':>20}\n")

    printer.set(align="center")
    printer.text("Thank you! Visit again.\n")
    if invoice.business_phone:
        printer.text(f"Orders: {invoice.business_phone}\n")

    try:
        printer.cut()
    except Exception:
        pass

    printer.close()


def print_receipt(order, customer, items, total, gst_total, advance, balance,
                  invoice_number: str, delivery_type: str,
                  delivery_address: str = "") -> None:
    """
    Legacy: prints from live objects. Kept for backwards compatibility.
    New code should build a snapshot via create_invoice() and call
    print_receipt_snapshot() instead.
    """
    printer = get_printer()
    width = _line_width()

    printer.set(align="center", bold=True)
    printer.text(settings.app_name.upper() + "\n")
    printer.set(bold=False)
    if settings.address:
        printer.text(settings.address + "\n")
    if settings.phone:
        printer.text(settings.phone + "\n")
    if settings.fssai_number:
        printer.text(f"FSSAI: {settings.fssai_number}\n")
    if settings.gstin:
        printer.text(f"GSTIN: {settings.gstin}\n")

    printer.set(align="left")
    printer.text("-" * width + "\n")
    printer.text(f"INV: {invoice_number}\n")
    printer.text(f"Date: {order.order_date.strftime('%d-%m-%Y %H:%M')}\n")
    printer.text(f"Customer: {customer.name}\n")
    printer.text(f"Phone: {customer.phone}\n")

    if delivery_type == "DELIVERY" and delivery_address:
        printer.text(f"Deliver To: {delivery_address}\n")
    else:
        printer.text("Type: PICKUP\n")

    printer.text("-" * width + "\n")

    for item in items:
        name = item.product.name
        max_name = 28 if width >= 48 else 20
        if len(name) > max_name:
            name = name[: max_name - 1] + "."
        if width >= 48:
            printer.text(f"{name:<28}{item.quantity:>4}{item.unit_price:>8.2f}{item.line_total:>8.2f}\n")
        else:
            printer.text(f"{name:<20}{item.quantity:>3}{item.line_total:>9.2f}\n")
        if item.customization_notes:
            printer.text(f"  Note: {item.customization_notes}\n")

    printer.text("-" * width + "\n")
    printer.text(f"Subtotal:{total - gst_total:>22.2f}\n")
    if settings.gstin and gst_total > 0:
        half = gst_total / 2
        printer.text(f"CGST:{half:>26.2f}\n")
        printer.text(f"SGST:{half:>26.2f}\n")

    printer.set(bold=True)
    printer.text(f"TOTAL:{total:>23.2f}\n")
    printer.set(bold=False)
    printer.text(f"Paid:{advance:>24.2f}\n")
    if balance > 0:
        printer.text(f"Balance Due:{balance:>17.2f}\n")
    else:
        printer.text(f"Balance Due:{'PAID':>20}\n")

    printer.set(align="center")
    printer.text("Thank you! Visit again.\n")
    if settings.phone:
        printer.text(f"Orders: {settings.phone}\n")

    try:
        printer.cut()
    except Exception:
        pass

    printer.close()
