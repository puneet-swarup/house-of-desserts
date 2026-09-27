# House of Desserts

A self-hosted operations system for a small bakery.

Built for speed, offline-friendly operation, and zero infrastructure cost.
Runs on a free-tier cloud VM, reachable from any device via Tailscale.
Covers order management, recipe-driven inventory, invoicing, tax-ready
reports, and WhatsApp-based customer communication.

## What it does

**Orders and customers**
- Full lifecycle: INQUIRY → CONFIRMED → IN_PROGRESS → READY → DELIVERED → PAID, or CANCELLED
- Edit while CONFIRMED, with audit trail and a floor guard against reducing below paid
- Search by order number, customer name, or phone
- Today page: dispatch list (orders fulfilling today, sorted by time) + production needs aggregated by SKU across the next 7 days

**Products and recipes**
- SKU auto-generated from name + weight + pack, editable, live uniqueness check
- Weight/volume and pack size support
- Recipe = ingredient BOM per SKU. Cost and capacity computed live from ingredient stock
- Unit conversion across mass (g ↔ kg) and volume (ml ↔ l). Count units (`pcs`, `packets`) are each their own group

**Inventory**
- Append-only stock movement ledger. Stock is a sum, never a stored balance
- Movements: PURCHASE, CONSUMPTION, WASTAGE, RETURN, ADJUSTMENT
- Opening stock at ingredient creation
- Auto-deduction on order IN_PROGRESS, per recipe
- Shortage warnings before starting production (does not block)
- Cancel-from-IN_PROGRESS with salvage (return stock) or waste
- Per-order COGS captured at consumption time, immune to future price changes
- Low-stock alert card on Today
- Weighted-average ingredient cost, updated on every purchase

**Money and documents**
- Payments tracked separately from fulfillment — two independent states
- Invoices are immutable snapshots. Editing the order does not change the invoice
- Sequential invoice numbering from a gapless sequence table
- Monthly reports (PDF + CSV): revenue, GST, COGS, gross margin, top products with unit economics, itemized orders
- Automatic report generation on the 1st of each month

**Operations**
- WhatsApp links (configurable templates, no API keys)
- Audit log: append-only, written in the same transaction as the mutation
- Nightly backups: local (30-day retention) + Google Drive via rclone
- Tailscale-only access in production. Zero ports open to the public internet

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+ / FastAPI |
| Database | SQLite (WAL) / SQLAlchemy 2.0 / Alembic |
| Templates | Jinja2 + HTMX + daisyUI |
| PDF | fpdf2 (Noto font for ₹) |
| Printing | python-escpos |
| Config | pydantic-settings |
| Remote access | Tailscale |
| Hosting | Oracle Cloud Free Tier (or any Linux VM) |
| Offsite backups | rclone → Google Drive |

## Quick start (local dev)

```powershell
git clone https://github.com/puneet-swarup/house-of-desserts.git
cd house-of-desserts

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e ".[dev]"

Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Paste output into SECRET_KEY in .env

alembic upgrade head

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 — redirects to `/today`.

## Configuration

All settings live in `.env`. See `.env.example` for the full list.

| Variable | Purpose |
|---|---|
| `APP_NAME`, `APP_TAGLINE` | Shown on invoices and the UI |
| `GSTIN`, `FSSAI_NUMBER` | Printed on invoices if set |
| `SECRET_KEY` | Session signing. **Required** — generate a real one |
| `DEBUG` | `true` in dev, `false` in prod |
| `BUSINESS_TIMEZONE` | "Today" boundaries, default `Asia/Kolkata` |
| `DB_URL` | SQLite path. Use absolute paths in production |
| `BIND_HOST`, `BIND_PORT` | Where uvicorn listens |
| `PRINTER_TYPE` | `file`, `usb`, or `network` |
| `BACKUP_DIR` | Where nightly SQLite backups are written |
| `REPORTS_DIR` | Where monthly PDFs and CSVs are written |
| `WHATSAPP_ENABLED` | Toggle WhatsApp buttons |
| `WHATSAPP_MESSAGES_FILE` | Path to message templates JSON |
| `WHATSAPP_DEFAULT_COUNTRY_CODE` | For phone normalization, default `91` |

## Data model

| Table | Purpose |
|---|---|
| `customers` | Soft delete via `is_active`, partial unique index on phone |
| `addresses` | Multiple per customer, exactly one default |
| `products` | Soft delete, weight/volume, pack size, GST rate |
| `ingredients` | Raw materials and packaging. Unit, threshold, weighted-average cost |
| `product_ingredients` | Recipe BOM. Quantity stored in the ingredient's own unit |
| `stock_movements` | Append-only ledger. Every stock change is a row |
| `orders` | Human-readable `HOD-YYYY-NNNN` number from a sequence table |
| `order_items` | Frozen unit price, GST rate, GST amount, line total (all `Numeric`) |
| `payments` | One row per transaction, explicit `received_at` |
| `invoices` | Immutable snapshot: business, billed-to, line items as JSON, all totals |
| `number_sequences` | Monotonic counter per prefix; gapless numbering |
| `audit_log` | Append-only; commits with the mutation it describes |
| `alembic_version` | Auto-managed by Alembic. Never edit or delete manually. |

## Development

```powershell
# Fast tests (no browser) — ~5 seconds
pytest

# Browser UI tests — ~50 seconds
pytest tests/ui -v

# Lint
ruff check app tests

# Pre-commit (before every commit)
pre-commit run --all-files

# CSS rebuild (after template class changes)
.\build-css.ps1
```

### Database migrations

Schema changes go through Alembic. The dev workflow:

1. Edit a model
2. `alembic revision --autogenerate -m "add foo to bar"`
3. **Review the generated file.** Autogenerate usually works but can miss server defaults or partial indexes.
4. `alembic upgrade head`
5. Run tests
6. Commit the model change + the migration file

Never edit an applied migration. Create a new one that changes what needs changing.

### Project layout

```
app/
  config.py              Typed settings from .env
  database.py            Engine, session, PRAGMAs
  main.py                App factory, routers, Jinja filters
  middleware.py          Cache-control headers
  models/                SQLAlchemy 2.0 declarative models
  routers/               HTTP endpoints
  services/              Business logic
  utils/
    money.py             Decimal helpers
    time.py              Naive-UTC storage + business-tz display
    sku.py               SKU generation
    units.py             Unit groups and conversion
    escpos_printer.py    Thermal printer
  templates/             Jinja2 + HTMX + daisyUI
  static/                Pre-built Tailwind, fonts, favicon

alembic/                 Migrations
config/
  messages.json          WhatsApp message templates
scripts/
  backup.py              Nightly backup script
  monthly_report.py      Monthly report generator
  build-css.ps1          (at repo root) CSS rebuild

tests/
  conftest.py            Fixtures (in-memory SQLite with FK ON)
  ui/                    Playwright browser tests
  ...
```

## Key design decisions

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the invariants that must not be broken.

- **Money is `Decimal`.** Columns are `Numeric(12,2)`. All arithmetic goes through `app.utils.money`.
- **Invoices are immutable.** Editing an order after issue does not change the invoice.
- **Numbering comes from a sequence table.** Concurrency-safe and gapless.
- **Audit writes commit with the mutation.** `log_action` never commits on its own.
- **Foreign keys are enforced** via `PRAGMA foreign_keys=ON` on every connection.
- **Inventory is a ledger.** `on_hand` is `SUM(delta)` over `stock_movements`.
- **Recipe quantities are always in the ingredient's own unit.** Conversion happens at the boundary.
- **Fulfillment and payment are orthogonal.** Two state machines, two badges.

## Operations

- Local: see [docs/OPERATIONS.md](docs/OPERATIONS.md)
- Deployment, recovery, and cron: in a private companion repo (coordinates and secrets)

## License

All rights reserved. This source is published for portfolio and evaluation
purposes only. See [LICENSE](LICENSE) for terms.

## Scope

This project is deliberately narrow: single-tenant, single-location, home-bakery
scale. It will not scale to a chain, doesn't do multi-user roles, and doesn't
attempt general-purpose e-commerce. If you need any of those, this is the wrong
tool. If you're a home baker who wants to run your kitchen without renting
infrastructure, it's the right one.
