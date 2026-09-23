"""
Customer CRUD + Address management routes.

Address rules:
- Multiple addresses per customer (one-to-many)
- Only ONE default at a time
- Soft delete (is_active=False), never hard delete
- New addresses added via form (list fields: addr_new_label, addr_new_line, addr_new_default)
- Existing addresses edited inline (addr_edit_{id}_label, addr_edit_{id}_line)
- Set default / soft delete via AJAX (return JSON, no redirect)
"""

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer, Address
from app.services import customer_service
from app.services.audit_service import log_action

router = APIRouter()


# ============================================================
# CUSTOMER ROUTES
# ============================================================

@router.get("/", response_class=HTMLResponse)
def list_page(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings
    customers = customer_service.list_customers(db)
    return templates.TemplateResponse(
        request=request,
        name="customers/list.html",
        context={"settings": settings, "customers": customers},
    )


@router.get("/new", response_class=HTMLResponse)
def new_form(request: Request):
    templates = request.app.state.templates
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="customers/form.html",
        context={"settings": settings, "customer": None},
    )


@router.get("/search", response_class=HTMLResponse)
def search_customers(request: Request, q: str = "", db: Session = Depends(get_db)):
    """Typeahead search for order form. Must be BEFORE /{customer_id}."""
    templates = request.app.state.templates

    if len(q.strip()) < 2:
        return ""

    q_clean = q.strip()
    phone_digits = ''.join(c for c in q_clean if c.isdigit())

    conditions = [Customer.name.ilike(f"%{q_clean}%")]
    if len(phone_digits) >= 3:
        conditions.append(Customer.phone.ilike(f"%{phone_digits}%"))

    results = db.execute(
        select(Customer)
        .where(or_(*conditions), Customer.is_active == True)  # ← ADD THIS
        .order_by(Customer.name)
        .limit(10)
    ).scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="customers/search_results.html",
        context={"results": results, "q": q_clean},
    )


@router.post("/", response_class=HTMLResponse)
async def create(
    request: Request,
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates
    settings = request.app.state.settings

    form = await request.form()

    name = form.get("name", "")
    phone = form.get("phone", "")
    email = form.get("email") or None
    notes = form.get("notes") or None
    addr_new_labels = form.getlist("addr_new_label") or ["Home"]
    addr_new_lines = form.getlist("addr_new_line") or [""]
    addr_new_defaults = form.getlist("addr_new_default") or [""]

    data = {"name": name, "phone": phone, "email": email, "notes": notes}

    try:
        customer = customer_service.create_customer(db, data)
    except Exception as e:
        return templates.TemplateResponse(
            request=request, name="customers/form.html",
            context={"settings": settings, "customer": None, "error": str(e)},
            status_code=400,
        )

    _process_new_addresses(db, customer.id, addr_new_labels, addr_new_lines, addr_new_defaults)

    log_action(db, entity_type="Customer", entity_id=customer.id, action="CREATE",
               new_value={"name": name, "phone": phone})
    return RedirectResponse(url="/customers", status_code=303)


@router.get("/{customer_id}", response_class=HTMLResponse)
def detail(request: Request, customer_id: int, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings
    customer = customer_service.get_customer(db, customer_id)
    return templates.TemplateResponse(
        request=request,
        name="customers/detail.html",
        context={"settings": settings, "customer": customer},
    )


@router.get("/{customer_id}/edit", response_class=HTMLResponse)
def edit_form(request: Request, customer_id: int, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings
    customer = customer_service.get_customer(db, customer_id)
    return templates.TemplateResponse(
        request=request,
        name="customers/form.html",
        context={"settings": settings, "customer": customer},
    )


@router.post("/{customer_id}/edit", response_class=HTMLResponse)
async def update(
    request: Request,
    customer_id: int,
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates
    settings = request.app.state.settings

    # Parse ALL form data manually
    form = await request.form()

    name = form.get("name", "")
    phone = form.get("phone", "")
    email = form.get("email") or None
    notes = form.get("notes") or None

    # New addresses (list fields — same name repeated)
    addr_new_labels = form.getlist("addr_new_label") or ["Home"]
    addr_new_lines = form.getlist("addr_new_line") or [""]
    addr_new_defaults = form.getlist("addr_new_default") or [""]

    data = {"name": name, "phone": phone, "email": email, "notes": notes}

    try:
        customer = customer_service.update_customer(db, customer_id, data)
    except Exception as e:
        customer = customer_service.get_customer(db, customer_id)
        return templates.TemplateResponse(
            request=request, name="customers/form.html",
            context={"settings": settings, "customer": customer, "error": str(e)},
            status_code=400,
        )

    # Process edited existing addresses: addr_edit_{id}_label, addr_edit_{id}_line
    _process_edited_addresses(db, customer_id, dict(form))

    # Process new addresses
    _process_new_addresses(db, customer_id, addr_new_labels, addr_new_lines, addr_new_defaults)

    log_action(db, entity_type="Customer", entity_id=customer_id, action="UPDATE",
               new_value={"name": name, "phone": phone})
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)

@router.post("/{customer_id}/delete")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    """Soft delete customer + cascade addresses. Returns JSON."""
    customer_service.soft_delete_customer(db, customer_id)
    return JSONResponse({"ok": True})

@router.get("/", response_class=HTMLResponse)
def list_page(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = request.app.state.settings
    customers = customer_service.list_customers(db, include_inactive=True)
    return templates.TemplateResponse(
        request=request,
        name="customers/list.html",
        context={"settings": settings, "customers": customers},
    )

# ============================================================
# ADDRESS AJAX ROUTES (return JSON, no redirect)
# ============================================================

@router.post("/{customer_id}/addresses/{addr_id}/set-default")
def set_default_address(customer_id: int, addr_id: int, db: Session = Depends(get_db)):
    """Set one address as default, clear all others. Instant, via AJAX."""
    customer = customer_service.get_customer(db, customer_id)
    for addr in customer.addresses:
        if addr.is_active:
            addr.is_default = (addr.id == addr_id)
    db.commit()
    return JSONResponse({"ok": True})


@router.post("/{customer_id}/addresses/{addr_id}/delete")
def soft_delete_address(customer_id: int, addr_id: int, db: Session = Depends(get_db)):
    """Soft delete: is_active=False. Row stays in DB. Via AJAX."""
    addr = db.get(Address, addr_id)
    if addr and addr.customer_id == customer_id:
        addr.is_active = False
        db.commit()
        log_action(db, entity_type="Address", entity_id=addr_id, action="DELETE",
                   old_value={"label": addr.label, "line": addr.line})
    return JSONResponse({"ok": True})


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _process_new_addresses(db: Session, customer_id: int, labels: list[str], lines: list[str], defaults: list[str]):
    has_new_default = False
    for i, line in enumerate(lines):
        if not line or not line.strip():
            continue
        is_def = (i < len(defaults) and defaults[i] == "1")
        if is_def and not has_new_default:
            has_new_default = True

    if has_new_default:
        existing = db.execute(
            select(Address).where(Address.customer_id == customer_id, Address.is_active == True)
        ).scalars().all()
        for a in existing:
            a.is_default = False

    default_assigned = False  # ← ADD THIS
    for i, line in enumerate(lines):
        if not line or not line.strip():
            continue
        label = labels[i].strip() if i < len(labels) else "Home"
        is_def = (i < len(defaults) and defaults[i] == "1") and not default_assigned  # ← ADD "and not default_assigned"
        if is_def:
            default_assigned = True  # ← ADD THIS
        db.add(Address(
            customer_id=customer_id,
            label=label or "Home",
            line=line.strip(),
            is_default=is_def,
        ))
    db.commit()


def _process_edited_addresses(db: Session, customer_id: int, kwargs: dict):
    """
    Update existing address fields from form submission.
    Expects keys like: addr_edit_3_label, addr_edit_3_line
    """
    for key, value in kwargs.items():
        if not key.startswith("addr_edit_"):
            continue
        if not value or not value.strip():
            continue
        parts = key.split("_")
        # addr_edit_{id}_{field}
        if len(parts) < 4:
            continue
        try:
            addr_id = int(parts[2])
            field = parts[3]  # "label" or "line"
        except (ValueError, IndexError):
            continue

        if field not in ("label", "line"):
            continue

        addr = db.get(Address, addr_id)
        if addr and addr.customer_id == customer_id and addr.is_active:
            setattr(addr, field, value.strip())
    db.commit()