# 🧁 House of Desserts — Order Management System

A lightweight, self-hosted order management system for a home bakery.
Built for speed, simplicity, and zero infrastructure cost.

## Features

- **Order Management** — Full lifecycle: Inquiry → Confirmed → In Progress → Ready → Delivered → Paid → Cancelled
- **Customer Book** — Contact details, multiple addresses (with default), preferences, order history
- **Product Catalog** — SKU, HSN code, GST rate, pricing, prep time, soft delete
- **Payment Tracking** — Advances, balance due, multiple payment methods, auto-PAID on full payment
- **Invoicing** — Thermal receipt (ESC/POS) + PDF (fpdf2) + on-screen preview
- **Delivery Management** — Pickup/Delivery toggle, address auto-population from customer records
- **Audit Log** — Append-only record of all changes (create, update, delete, status change, payment)
- **Monthly Export** — CSV (orders, payments) + JSON (summary) for tax filing
- **Soft Delete** — Customers, products, and addresses are never hard-deleted
- **Mobile-Friendly** — Responsive UI, accessible from phone via Tailscale
- **Zero CDN Dependency** — All CSS/JS self-hosted, works offline

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+ + FastAPI |
| Database | SQLite + SQLAlchemy 2.0 (ORM) |
| Migrations | Alembic |
| Frontend | HTMX + daisyUI 4 (pre-compiled Tailwind CSS) |
| Templating | Jinja2 |
| PDF Generation | fpdf2 (pure Python, no system deps) |
| Thermal Printing | python-escpos (ESC/POS protocol) |
| Config | pydantic-settings (env vars) |
| Remote Access | Tailscale (free tier, MagicDNS) |
| Backup | SQLite online backup via Windows Task Scheduler |

## Quick Start

### Prerequisites

- Python 3.12+
- (Optional) A thermal receipt printer (80mm or 58mm)
- (Optional) Tailscale for remote access

### Setup

```bash
# 1. Clone the repo
git clone <your-repo-url> house-of-desserts
cd house-of-desserts

# 2. Create virtual environment
python -m venv .venv

# 3. Activate it
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# 4. Install all dependencies (including dev tools)
pip install -e ".[dev]"

# 5. Configure environment
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/Mac
# Edit .env with your business details

# 6. Create required directories
mkdir data backups

# 7. Run database migrations
alembic upgrade head

# 8. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload   
```

### Access
- Local: http://localhost:8000
- Tailscale (remote): http://houseofdesserts (port 80 via tailscale serve)
- Phone: Install Tailscale → open http://houseofdesserts in browser

### Configuration
All business details are configured via environment variables (.env file):

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_NAME` | Business name (shown in UI & receipts) | `House of Desserts` |
| `APP_TAGLINE` | Tagline/subtitle | `Artisan Bakes & Cakes` |
| `FSSAI_NUMBER` | FSSAI license number | `10012345678901` |
| `GSTIN` | GSTIN (if registered, leave blank if not) | `27ABCDE1234F1Z5` |
| `PHONE` | Business phone | `+91 98765 43210` |
| `ADDRESS` | Business address | `12 Baker's Lane, Mumbai` |
| `CURRENCY` | Currency symbol | `₹` |
| `DB_URL` | Database connection string | `sqlite:///data/bakery.db` |
| `PRINTER_TYPE` | `usb`, `network`, or `file` | `file` |
| `PRINTER_DEVICE` | USB path or IP:port | `192.168.1.50:9100` |
| `PRINTER_WIDTH` | Paper width in mm (58 or 80) | `80` |
| `BACKUP_DIR` | Directory for DB backups | `./backups` |
| `INVOICE_PREFIX` | Invoice number prefix | `HOD` |
| `INVOICE_START_NUMBER` | Starting sequence number | `1` |

### Project Structure

```
house-of-desserts/
├── app/
│   ├── main.py              # FastAPI app factory & router registration
│   ├── config.py            # Settings (loaded from .env via pydantic-settings)
│   ├── database.py          # SQLAlchemy engine, session, Base
│   ├── models/              # ORM models (one file per entity)
│   │   ├── customer.py      # Customer (soft delete: is_active)
│   │   ├── address.py       # Address (one-to-many with Customer, soft delete)
│   │   ├── product.py       # Product (SKU, HSN, GST rate, soft delete)
│   │   ├── order.py         # Order + OrderItem + OrderStatus enum
│   │   ├── payment.py       # Payment records
│   │   ├── invoice.py       # Invoice records
│   │   └── audit_log.py     # Append-only audit trail
│   ├── schemas/             # Pydantic request/response schemas
│   ├── routers/             # HTTP route handlers
│   │   ├── dashboard.py     # Stats + recent orders
│   │   ├── products.py      # Product CRUD
│   │   ├── customers.py     # Customer CRUD + address management + search
│   │   ├── orders.py        # Order CRUD + status + payments
│   │   ├── invoices.py      # PDF, thermal print, preview
│   │   ├── export.py        # CSV/JSON downloads
│   │   ├── audit.py         # Audit log viewer
│   │   └── settings.py      # Business config display
│   ├── services/            # Business logic
│   │   ├── product_service.py
│   │   ├── customer_service.py
│   │   ├── order_service.py
│   │   ├── invoice_service.py
│   │   ├── export_service.py
│   │   └── audit_service.py
│   ├── templates/           # Jinja2 + HTMX + daisyUI HTML
│   ├── static/
│   │   ├── css/app.css      # Pre-compiled Tailwind + daisyUI
│   │   ├── js/htmx.min.js   # Self-hosted HTMX
│   │   └── images/logo.png
│   └── utils/
│       └── escpos_printer.py  # Thermal printer wrapper
├── alembic/                 # Database migrations
├── tests/                   # Pytest test suite (40+ tests)
├── docs/
│   └── adr/                 # Architecture Decision Records
├── data/                    # SQLite DB + generated PDFs (gitignored)
├── backups/                 # DB backup files (gitignored)
├── backup.py                # Nightly backup script
├── backup.bat               # Windows Task Scheduler wrapper
├── .env.example             # Template for environment config
├── pyproject.toml           # Project metadata & dependencies
└── Makefile                 # Common commands   
```

### Development
```
# Run tests
pytest -v

# Run with hot reload (development)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rebuild CSS (after adding new Tailwind classes in templates)
cd app\static\css
tailwindcss.exe -i input.css -o app.css --minify

# Watch mode for CSS (during development)
tailwindcss.exe -i input.css -o app.css --minify --watch   
```

## Deployment
### Tailscale Remote Access
```
# Install Tailscale on your PC + phone, sign in with same account
# Rename machine to "houseofdesserts" in Tailscale admin
# Enable MagicDNS in Tailscale admin

# Serve on port 80 (proxies to your app on 8000)
tailscale serve --bg 80   
```

### Nightly Backup
```
# Manual backup
backup.bat

# Scheduled: Windows Task Scheduler → Daily at 2 AM
# Program: backup.bat
# Start in: project root   
```

```html
Keeps last 7 backups. Log at backups/backup.log.
```

## Backup & Recovery
```html
# Manual backup
sqlite3 data/bakery.db ".backup 'backups/bakery_$(date +%Y%m%d).db'"

# Restore
sqlite3 data/bakery.db ".restore 'backups/bakery_20260922.db'"   
```

## Roadmap
- [x] Core CRUD (Products, Customers, Orders)
- [x] Multi-address per customer with default
- [x] Customer typeahead search
- [x] Delivery/Pickup toggle with address auto-population
- [x] Payment tracking + auto-PAID
- [x] Thermal receipt printing (ESC/POS)
- [x] PDF invoice generation (fpdf2)
- [x] Invoice preview (on-screen)
- [x] CSV/JSON export for tax filing
- [x] Audit log (auto + viewer)
- [x] Soft delete (customers, products, addresses)
- [x] Responsive mobile UI
- [x] Tailscale remote access
- [x] Nightly backup automation
- [x] Test suite (40+ tests)
- [ ] (Phase 2) WhatsApp webhook integration
- [ ] (Phase 2) Order editing (INQUIRY/CONFIRMED states)
- [ ] (Phase 2) Product search in order form (50+ products)
- [ ] (Phase 3) Recipe/ingredient costing
- [ ] (Phase 3) Customer-facing portal

## License
Private — All rights reserved.