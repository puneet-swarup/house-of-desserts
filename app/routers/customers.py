"""
Customer CRUD + Address routes.

Address rules:
- Multiple addresses per customer
- Only ONE default at a time
- Soft delete (is_active=False)
- First-ever address is ALWAYS default
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Address, Customer
from app.services import customer_service
from app.services.audit_service import log_action

router = APIRouter()


# ============================================================
# CUSTOMER ROUTES
# ============================================================

@router.get("/", response_class=HTMLResponse)
def list_page(
    request: Request,
    q: str = "",
    page: int = 1,
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates
    settings = request.app.state.settings
    customers, meta = customer_service.search_customers(db, q=q, page=page)
    return templates.TemplateResponse(
        request=request,
        name="customers/list.html",
        context={"settings": settings, "customers": customers, "meta": meta},
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
        return HTMLResponse("")

    q_clean = q.strip()
    phone_digits = "".join(c for c in q_clean if c.isdigit())

    conditions = [Customer.name.ilike(f"%{q_clean}%")]
    if len(phone_digits) >= 3:
        conditions.append(Customer.phone.ilike(f"%{phone_digits}%"))

    results = (
        db.execute(
            select(Customer)
            .where(or_(*conditions), Customer.is_active.is_(True))
            .order_by(Customer.name)
            .limit(10)
        )
        .scalars()
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="customers/search_results.html",
        context={"results": results, "q": q_clean},
    )


@router.post("/quick")
async def quick_add(request: Request, db: Session = Depends(get_db)):
    """
    Quick-add customer from the order-form modal.
    Returns JSON {ok, customer:{id,name,phone,default_address}} or {ok:false,error}.
    """
    form = await request.form()
    name = (form.get("name") or "").strip()
    phone = (form.get("phone") or "").strip()
    email = (form.get("email") or "").strip() or None
    address_line = (form.get("address_line") or "").strip()
    address_label = (form.get("address_label") or "Home").strip() or "Home"

    if not name or not phone:
        return JSONResponse(
            {"ok": False, "error": "Name and phone are required"},
            status_code=400,
        )

    try:
        customer = customer_service.create_customer(
            db,
            {"name": name, "phone": phone, "email": email, "notes": None},
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

    if address_line:
        try:
            customer_service.add_address(
                db,
                customer.id,
                {"label": address_label, "line": address_line, "is_default": True},
            )
        except Exception:
            pass

    db.refresh(customer)
    return JSONResponse(
        {
            "ok": True,
            "customer": {
                "id": customer.id,
                "name": customer.name,
                "phone": customer.phone,
                "default_address": customer.default_address_line,
            },
        }
    )


@router.post("/", response_class=HTMLResponse)
async def create(request: Request, db: Session = Depends(get_db)):
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
            request=request,
            name="customers/form.html",
            context={"settings": settings, "customer": None, "error": str(e)},
            status_code=400,
        )

    _process_new_addresses(
        db, customer.id, addr_new_labels, addr_new_lines, addr_new_defaults
    )
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
async def update(request: Request, customer_id: int, db: Session = Depends(get_db)):
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
        customer = customer_service.update_customer(db, customer_id, data)
    except Exception as e:
        customer = customer_service.get_customer(db, customer_id)
        return templates.TemplateResponse(
            request=request,
            name="customers/form.html",
            context={"settings": settings, "customer": customer, "error": str(e)},
            status_code=400,
        )

    _process_edited_addresses(db, customer_id, dict(form))
    _process_new_addresses(
        db, customer_id, addr_new_labels, addr_new_lines, addr_new_defaults
    )
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@router.post("/{customer_id}/delete")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    customer_service.soft_delete_customer(db, customer_id)
    return JSONResponse({"ok": True})


# ============================================================
# ADDRESS AJAX ROUTES
# ============================================================

@router.post("/{customer_id}/addresses/{addr_id}/set-default")
def set_default_address(customer_id: int, addr_id: int, db: Session = Depends(get_db)):
    try:
        customer_service.set_default_address(db, customer_id, addr_id)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@router.post("/{customer_id}/addresses/{addr_id}/delete")
def soft_delete_address(customer_id: int, addr_id: int, db: Session = Depends(get_db)):
    addr = db.get(Address, addr_id)
    if addr and addr.customer_id == customer_id:
        addr.is_active = False
        db.commit()
        log_action(
            db,
            entity_type="Address",
            entity_id=addr_id,
            action="DELETE",
            old_value={"label": addr.label, "line": addr.line},
        )
    return JSONResponse({"ok": True})


# ============================================================
# HELPERS
# ============================================================

def _process_new_addresses(db, customer_id, labels, lines, defaults):
    """
    Rules:
      - First EVER address for a customer is always default
      - If any new row is marked default, demote all existing
      - At most one new row is marked default
    """
    existing = (
        db.execute(
            select(Address).where(
                Address.customer_id == customer_id,
                Address.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    has_existing = len(existing) > 0

    rows = []
    for i, line in enumerate(lines):
        if not line or not line.strip():
            continue
        label = labels[i].strip() if i < len(labels) else "Home"
        is_def = i < len(defaults) and defaults[i] == "1"
        rows.append({"label": label or "Home", "line": line.strip(), "is_def": is_def})

    if not rows:
        return

    if not has_existing:
        rows[0]["is_def"] = True

    if any(r["is_def"] for r in rows):
        for a in existing:
            a.is_default = False
        seen = False
        for r in rows:
            if r["is_def"]:
                if seen:
                    r["is_def"] = False
                else:
                    seen = True

    for r in rows:
        db.add(
            Address(
                customer_id=customer_id,
                label=r["label"],
                line=r["line"],
                is_default=r["is_def"],
            )
        )
    db.commit()


def _process_edited_addresses(db, customer_id, kwargs):
    for key, value in kwargs.items():
        if not key.startswith("addr_edit_"):
            continue
        if not value or not value.strip():
            continue
        parts = key.split("_")
        if len(parts) < 4:
            continue
        try:
            addr_id = int(parts[2])
            field = parts[3]
        except (ValueError, IndexError):
            continue
        if field not in ("label", "line"):
            continue
        addr = db.get(Address, addr_id)
        if addr and addr.customer_id == customer_id and addr.is_active:
            setattr(addr, field, value.strip())
    db.commit()
