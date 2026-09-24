"""
WhatsApp link builder.

Design:
- Uses wa.me universal links — no API, no auth, works on desktop and mobile.
- Messages are plain text templates read from config/messages.json on each
  call. Editing that file takes effect immediately, no restart.
- Phone numbers are normalized to digits-only with country code prepended.
  If a number can't be normalized, the message is unavailable and the UI
  hides the button.

Replacing this with an SMS/Twilio provider later: only build_wa_url() and
messages_for_order() need to change. Templates and context stay the same.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from app.config import get_settings
from app.utils.time import to_business_tz

DEFAULT_MESSAGES: dict[str, str] = {
    "confirmed": (
        "Hi {customer_first_name}, your order {order_number} for {total} is confirmed. "
        "Expected {fulfillment_datetime}. — {business_name}"
    ),
    "ready": (
        "Hi {customer_first_name}, your order {order_number} is ready for "
        "{delivery_or_pickup}. {fulfillment_datetime}. — {business_name}"
    ),
    "out_for_delivery": (
        "Hi {customer_first_name}, your order {order_number} is on the way to "
        "{delivery_address}. Balance due on delivery: {balance}. — {business_name}"
    ),
    "delivered": (
        "Hi {customer_first_name}, your order {order_number} has been delivered. "
        "Thanks for choosing {business_name}!"
    ),
    "payment_reminder": (
        "Hi {customer_first_name}, a gentle reminder — balance of {balance} on "
        "order {order_number} is pending. Total {total}, paid {paid}. — {business_name}"
    ),
    "custom": "Hi {customer_first_name}, ",
}

TRIGGER_LABELS: dict[str, str] = {
    "confirmed": "Order confirmed",
    "ready": "Order is ready",
    "out_for_delivery": "Out for delivery",
    "delivered": "Delivered — thank you",
    "payment_reminder": "Payment reminder",
    "custom": "Custom message",
}


# ---------------------------------------------------------------
# Message file loading (mtime-cached)
# ---------------------------------------------------------------

_cache: dict[str, str] | None = None
_cache_mtime: float = 0.0
_cache_path: str = ""


def load_messages(path: str | None = None) -> dict[str, str]:
    """
    Load message templates, merging user overrides on top of defaults.
    Reloads automatically when the file's mtime changes.
    """
    global _cache, _cache_mtime, _cache_path
    settings = get_settings()
    p = Path(path or settings.whatsapp_messages_file)

    if not p.exists():
        return dict(DEFAULT_MESSAGES)

    try:
        mtime = p.stat().st_mtime
    except OSError:
        return dict(DEFAULT_MESSAGES)

    if _cache is not None and _cache_path == str(p) and mtime == _cache_mtime:
        return _cache

    try:
        with p.open("r", encoding="utf-8") as f:
            user = json.load(f)
        if not isinstance(user, dict):
            user = {}
    except (json.JSONDecodeError, OSError):
        user = {}

    merged = dict(DEFAULT_MESSAGES)
    for k, v in user.items():
        if isinstance(v, str) and v.strip():
            merged[k] = v

    _cache = merged
    _cache_mtime = mtime
    _cache_path = str(p)
    return merged


# ---------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------


def normalize_phone(raw: str | None, default_cc: str = "91") -> str:
    """
    Return digits-only phone with country code, ready for wa.me.
    Returns "" if the number can't be normalized.

    Examples (default_cc="91"):
      "+91 98765 43210"  -> "919876543210"
      "9876543210"       -> "919876543210"
      "09876543210"      -> "919876543210"   (strips leading 0)
      "919876543210"     -> "919876543210"   (already has CC)
      ""                 -> ""
    """
    if not raw:
        return ""
    digits = "".join(c for c in raw if c.isdigit())
    if not digits:
        return ""

    # Strip a single leading 0 (Indian local dialing)
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    # 10 digits -> local mobile number, prepend country code
    if len(digits) == 10:
        return default_cc + digits

    # 11+ digits -> assume already includes country code
    if len(digits) >= 11:
        return digits

    # Too short — refuse
    return ""


# ---------------------------------------------------------------
# Context + rendering
# ---------------------------------------------------------------


def _fmt_money(v) -> str:
    settings = get_settings()
    try:
        return f"{settings.currency}{float(v):,.2f}"
    except (TypeError, ValueError):
        return ""


def _fmt_datetime(dt) -> str:
    if dt is None:
        return ""
    local = to_business_tz(dt)
    return local.strftime("%d %b %Y, %I:%M %p").replace(" 0", " ")


def build_context(order) -> dict:
    """Flatten an Order + Customer + Settings into template variables."""
    settings = get_settings()
    customer = order.customer
    name = (customer.name or "").strip()
    return {
        "customer_name": name,
        "customer_first_name": name.split()[0] if name else "",
        "order_number": order.order_number,
        "total": _fmt_money(order.total_amount),
        "paid": _fmt_money(order.advance_paid),
        "balance": _fmt_money(order.balance_due),
        "delivery_type": order.delivery_type,
        "delivery_or_pickup": "delivery" if order.delivery_type == "DELIVERY" else "pickup",
        "delivery_address": order.delivery_address or "",
        "fulfillment_datetime": _fmt_datetime(order.fulfillment_date),
        "business_name": settings.app_name,
        "business_phone": settings.phone,
        "business_address": settings.address,
    }


def render_message(template: str, context: dict) -> str:
    """Format a template with context. Missing keys render blank."""

    class _SafeDict(dict):
        def __missing__(self, key):
            return ""

    try:
        return template.format_map(_SafeDict(context))
    except (ValueError, IndexError):
        # Unbalanced braces etc. — return the raw template
        return template


def build_wa_url(phone: str, message: str) -> str:
    """Universal WhatsApp link — works on mobile app and web.whatsapp.com."""
    return f"https://wa.me/{phone}?text={quote(message)}"


def messages_for_order(order) -> list[dict]:
    """
    Return the list of available messages for an order, each with:
      {key, label, message, url}

    Filters by relevance:
      - out_for_delivery only for DELIVERY orders
      - payment_reminder only if balance > 0
      - others always available (except if phone can't be normalized)
    """
    settings = get_settings()

    if not settings.whatsapp_enabled:
        return []

    phone = normalize_phone(
        order.customer.phone,
        default_cc=settings.whatsapp_default_country_code,
    )
    if not phone:
        return []

    templates = load_messages()
    context = build_context(order)

    balance_positive = (order.balance_due or 0) > 0
    is_delivery = order.delivery_type == "DELIVERY"

    allowed = ["confirmed", "ready"]
    if is_delivery:
        allowed.append("out_for_delivery")
    allowed.append("delivered")
    if balance_positive:
        allowed.append("payment_reminder")
    allowed.append("custom")

    out = []
    for key in allowed:
        template = templates.get(key)
        if not template:
            continue
        text = render_message(template, context)
        out.append(
            {
                "key": key,
                "label": TRIGGER_LABELS.get(key, key.replace("_", " ").title()),
                "message": text,
                "url": build_wa_url(phone, text),
            }
        )
    return out
