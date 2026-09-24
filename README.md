# House of Desserts

A self-hosted order management system for a home bakery.

Built for speed, offline-first operation, and zero infrastructure cost.
Runs on a laptop or a mini PC on your home network and is reachable
from anywhere via Tailscale.

## Features

- **Order lifecycle** — INQUIRY → CONFIRMED → IN_PROGRESS → READY → DELIVERED → PAID, with CANCELLED as a terminal branch
- **Customer book** with multiple addresses and search
- **Product catalog** with SKU, HSN, GST rate, and soft delete
- **Payment tracking** — partial payments, auto-PAID on full settlement
- **Invoices** — immutable snapshots with sequential numbering, PDF export, and thermal receipt
- **Audit trail** — append-only log of every mutation, written in the same transaction as the mutation
- **Dashboard** — today's orders, pending delivery, outstanding balance, active products
- **Exports** — monthly CSV/JSON for tax filing
- **Thermal printer support** — file, USB, or network ESC/POS

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+ / FastAPI |
| Database | SQLite (WAL) / SQLAlchemy 2.0 |
| Templates | Jinja2 + HTMX + daisyUI |
| PDF | fpdf2 (Noto font for ₹) |
| Printing | python-escpos |
| Config | pydantic-settings |

## Quick start

```powershell
git clone https://github.com/puneet-swarup/house-of-desserts.git
cd house-of-desserts

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e ".[dev]"

Copy-Item .env.example .env
# Edit .env: set SECRET_KEY, DEBUG=false, optionally GSTIN etc.

python -c "import secrets; print(secrets.token_urlsafe(48))"
# Paste output into SECRET_KEY in .env

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

## Configuration

All configuration lives in `.env`. See `.env.example` for the full list.

| Variable | Purpose |
|---|---|
| `APP_NAME`, `APP_TAGLINE` | Shown on invoices and the UI |
| `GSTIN`, `FSSAI_NUMBER` | Printed on invoices if set |
| `SECRET_KEY` | Session signing. **Required** — generate a real one |
| `DEBUG` | `true` in dev, `false` in prod. `true` logs every SQL query |
| `BUSINESS_TIMEZONE` | Used for "today" and report boundaries, default `Asia/Kolkata` |
| `BIND_HOST`, `BIND_PORT` | Where uvicorn listens |
| `PRINTER_TYPE` | `file`, `usb`, or `network` |
| `BACKUP_DIR` | Where SQLite backups are written |

## Data model

- **Customer** — soft delete via `is_active`, partial unique index on phone
- **Address** — multiple per customer, one default
- **Product** — soft delete, partial unique index on SKU
- **Order** — human-readable `HOD-YYYY-NNNN` number from a sequence table
- **OrderItem** — frozen unit price, GST rate, GST amount, line total (all `Numeric`)
- **Payment** — one row per transaction, `received_at` explicit
- **Invoice** — immutable snapshot: business identity, billed-to, line items as JSON, and all totals as of issue time
- **NumberSequence** — monotonic counter per prefix; guarantees gapless numbering
- **AuditLog** — append-only; written in the same transaction as the mutation it describes

## Development

```powershell
# Run unit tests (fast, no browser)
pytest

# Run UI tests (requires running app)
pytest tests/ui -v
```

### Project layout

```
app/
  config.py              Typed settings from .env
  database.py            Engine, session, PRAGMAs, get_db dependency
  main.py                App factory, routers, filters
  models/                SQLAlchemy 2.0 declarative models
  schemas/               Pydantic request/response models
  routers/               HTTP endpoints
  services/              Business logic — called by routers
  utils/
    money.py             Decimal helpers
    time.py              Naive-UTC storage + business-tz display
    escpos_printer.py    Thermal printer
  templates/             Jinja2 + HTMX + daisyUI
  static/                Pre-built Tailwind, fonts, favicon

tests/
  conftest.py            Fixtures (in-memory SQLite with FK ON)
  test_money.py          Decimal rounding, GST split
  test_numbering.py      Sequential, gapless
  test_status_machine.py Legal/illegal transitions
  test_invoice_snapshot.py  Invoice is immutable
  test_soft_delete.py    Delete → recreate works
  test_fk_enforcement.py Proves PRAGMA is on
  ui/                    Playwright tests
```

## Key design decisions

- **Money is `Decimal`, never `Float`.** Columns are `Numeric(12,2)`. Every calculation goes through `app.utils.money.money()`. Rounding is per-line, half-up, and documented in `money.py`.
- **Invoices are immutable.** At issue time we snapshot business identity, billed-to, line items, and totals into the invoice row. Editing the order afterwards does not change the invoice.
- **Order and invoice numbers come from a sequence table**, not a count. Gapless, concurrency-safe, unique-constrained.
- **Audit writes commit with the mutation.** `log_action` never commits on its own. A failed audit write rolls back the whole transaction.
- **Foreign keys are enforced** via `PRAGMA foreign_keys=ON` on every connection. Cascade deletes work.
- **WAL + busy_timeout** so backups and app writes don't deadlock.
- **Naive UTC storage, business-tz display.** See `app/utils/time.py`.

## Operations

See [docs/OPERATIONS.md](docs/OPERATIONS.md) for backup, restore, deploy, and troubleshooting.

## License

Private — not for redistribution.