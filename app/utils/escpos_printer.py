r"""
Thermal printer utility using python-escpos.

PRINTER_TYPE options (from .env):
- "file"    → Writes to a .bin file (for testing without a physical printer)
- "usb"     → USB-connected printer
- "network" → LAN/TCP printer
"""

from pathlib import Path

from app.config import get_settings

settings = get_settings()


def get_printer():
    """Returns a configured escpos printer instance."""
    from escpos.printer import File, Usb, Network

    if settings.printer_type == "file":
        output_path = Path("data") / "receipt_preview.bin"
        output_path.parent.mkdir(exist_ok=True)
        return File(str(output_path))

    elif settings.printer_type == "usb":
        profile = "POS-58" if settings.printer_width == 58 else "POS-80"
        return Usb(device=1, usb_args=(None, None), profile=profile)

    elif settings.printer_type == "network":
        parts = settings.printer_device.split(":")
        ip = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 9100
        profile = "POS-58" if settings.printer_width == 58 else "POS-80"
        return Network(host=ip, port=port, profile=profile)

    else:
        raise ValueError(f"Unknown printer_type: {settings.printer_type}")


def print_receipt(order, customer, items, total, gst_total, advance, balance,
                  invoice_number: str, delivery_type: str, delivery_address: str = ""):
    """Generate and send a thermal receipt for the given order."""
    printer = get_printer()
    width = settings.printer_width
    line_width = 32 if width == 58 else 42

    # Header
    printer.set(align="center", bold=True)
    printer.text(settings.app_name.upper() + "\n")
    printer.set(bold=False)

    if settings.address:
        printer.set(align="center")
        printer.text(settings.address + "\n")
    if settings.phone:
        printer.text(settings.phone + "\n")
    if settings.fssai_number:
        printer.text(f"FSSAI: {settings.fssai_number}\n")
    if settings.gstin:
        printer.text(f"GSTIN: {settings.gstin}\n")

    printer.set(align="left")
    printer.text("-" * line_width + "\n")

    # Invoice info
    printer.text(f"INV: {invoice_number}  |  {order.order_date.strftime('%d-%m-%Y %H:%M')}\n")
    printer.text(f"Customer: {customer.name}\n")
    printer.text(f"Phone: {customer.phone}\n")

    # Delivery info
    if delivery_type == "DELIVERY" and delivery_address:
        printer.text(f"Deliver to: {delivery_address}\n")
        if order.delivery_date:
            printer.text(f"Date: {order.delivery_date.strftime('%d %b %Y')}\n")
    else:
        printer.text("Type: PICKUP\n")
        if order.delivery_date:
            printer.text(f"Ready: {order.delivery_date.strftime('%d %b %Y')}\n")

    printer.text("-" * line_width + "\n")

    # Items
    printer.set(bold=True)
    if width >= 80:
        printer.text(f"{'Item':<25} {'Qty':>3} {'Rate':>8} {'Amt':>8}\n")
    else:
        printer.text(f"{'Item':<20} {'Qty':>3} {'Amt':>7}\n")
    printer.set(bold=False)

    for item in items:
        name = item.product.name
        max_name = 25 if width >= 80 else 20
        if len(name) > max_name:
            name = name[:max_name - 1] + "…"

        if width >= 80:
            printer.text(f"{name:<25} {item.quantity:>3} {item.unit_price:>8.2f} {item.line_total:>8.2f}\n")
        else:
            printer.text(f"{name:<20} {item.quantity:>3} {item.line_total:>7.2f}\n")

        if item.customization_notes:
            printer.text(f"  Note: {item.customization_notes}\n")

    printer.text("-" * line_width + "\n")

    # Totals
    printer.text(f"Subtotal:              {total - gst_total:>10.2f}\n")

    if settings.gstin and gst_total > 0:
        gst_rate = items[0].product.gst_rate if items else 0
        half_rate = gst_rate / 2
        cgst = gst_total / 2
        sgst = gst_total / 2
        printer.text(f"CGST @ {half_rate}%:         {cgst:>10.2f}\n")
        printer.text(f"SGST @ {half_rate}%:         {sgst:>10.2f}\n")
        # Not registered: no GST lines

    printer.set(bold=True)
    printer.text(f"TOTAL:                 {total:>10.2f}\n")
    printer.set(bold=False)
    printer.text(f"Paid:                  {advance:>10.2f}\n")
    if balance > 0:
        printer.set(bold=True)
        printer.text(f"Balance Due:           {balance:>10.2f}\n")
        printer.set(bold=False)
    else:
        printer.text(f"Balance Due:             {'PAID':>10}\n")

        # Footer
    printer.set(align="center")
    printer.text("Thank you! Visit again.\n")
    if settings.phone:
        printer.text(f"Orders: {settings.phone}\n")

    try:
        printer.cut()
    except Exception:
        pass

    printer.close()   