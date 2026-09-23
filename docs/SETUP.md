# Development Setup Guide

This document explains how to set up the development environment from scratch.
Follow these steps in order.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | [python.org](https://python.org) or `brew install python@3.12` |
| Git | any | Pre-installed on most systems |
| (Optional) sqlite3 CLI | any | `brew install sqlite` / `sudo apt install sqlite3` |
| (Optional) Tailscale | latest | [tailscale.com](https://tailscale.com) for remote access |

## Quick Start (5 minutes)

```bash
# 1. Clone the repo
git clone <repo-url> house-of-desserts
cd house-of-desserts

# 2. Create virtual environment
python -m venv .venv

# 3. Activate it
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows (CMD)
# .venv\Scripts\Activate.ps1     # Windows (PowerShell)

# 4. Install all dependencies (including dev tools)
pip install -e ".[dev]"

# 5. Configure environment
cp .env.example .env
# Edit .env with your business details

# 6. Create required directories
mkdir -p data backups

# 7. Run database migrations
alembic upgrade head

# 8. Start the dev server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload   

Open http://localhost:8000 — you should see the app.
```

## PyCharm / IntelliJ Setup
- File → Open → select the project root folder
- When prompted for interpreter: Configure → Add → Virtualenv → Existing → point to .venv/bin/python
- Run → Edit Configurations → + → Python:
  - Module name: uvicorn
  - Parameters: app.main:app --host 0.0.0.0 --port 8000 --reload
  - Working directory: project root
- Click ▶ to run

## Common Commands
| Task | Command |
|------|---------|
| Start dev server | `uvicorn app.main:app --reload` |
| Run tests | `pytest -v` |
| Create new migration | `alembic revision --autogenerate -m "description"` |
| Apply migrations | `alembic upgrade head` |
| Rollback last migration | `alembic downgrade -1` |
| Backup database | `make backup` |
| Lint code | `ruff check app/` |
| Type check | `mypy app/` |

## Project Structure (what each folder does)
```
app/
├── main.py          → Entry point. Creates the FastAPI app, registers routers.
├── config.py        → All settings from .env. Single source of truth.
├── database.py      → Engine, Session, Base. The DB "plumbing."
├── models/          → SQLAlchemy ORM classes. One file per table.
├── schemas/         → Pydantic classes. Validate input, shape output.
├── routers/         → HTTP endpoints. Thin layer — calls services.
├── services/        → Business logic. The "brain" of the app.
├── templates/       → HTML files (Jinja2 + HTMX + daisyUI).
├── static/          → CSS, JS, images served to the browser.
└── utils/           → Helpers (printer, formatters). 

alembic/             → Database migration scripts (auto-generated).
tests/               → Pytest test files.
docs/adr/            → Architecture Decision Records (why we made choices).
data/                → SQLite database file lives here.
backups/             → Database backup files.   
```

## How to Add a New Feature (workflow)
- Model (app/models/): Define the SQLAlchemy class if a new table is needed.
- Migration: Run alembic revision --autogenerate -m "add_xxx", review the generated file, then alembic upgrade head.
- Schema (app/schemas/): Define Pydantic request/response models.
- Service (app/services/): Write the business logic.
- Router (app/routers/): Create the HTTP endpoint, call the service.
- Template (app/templates/): Create the HTML page (if it has a UI).
- Register router in app/main.py.
- Test: Add tests in tests/.

## Environment Variables
All configuration is in .env (never committed to git). See .env.example for the full list.
The app reads these via app/config.py (pydantic-settings).

## Troubleshooting
| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'app'` | You didn't run `pip install -e .` or your venv isn't activated. |
| `sqlite3.OperationalError: unable to open database file` | The `data/` directory doesn't exist. Run `mkdir -p data`. |
| `weasyprint` import error on Linux | `sudo apt install libpango-1.0-0 libpangocairo-1.0-0` |
| Port 8000 already in use | Kill the process: `lsof -i :8000` then `kill -9 <PID>`, or use a different port. |
| Alembic can't detect model changes | Make sure you import all models in `alembic/env.py`. |

## Tailscale Remote Access

### One-Time Setup

1. Create a free account at [tailscale.com](https://tailscale.com)
2. Install Tailscale on your **home PC** (Windows) and **phone** (Android/iOS)
3. Sign in with the same account on both
4. Go to [login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines)
   - Rename your PC to `houseofdesserts`
5. Go to [login.tailscale.com/admin/dns](https://login.tailscale.com/admin/dns)
   - Enable **MagicDNS**
6. On your PC, run:
   ```bash
   tailscale serve --bg 80
   ```
   
#### Access
- From phone (any network): http://houseofdesserts
- From PC (local): http://localhost:8000

#### Troubleshooting

| Problem | Fix |
|---------|-----|
| Can't connect from phone | Check Tailscale is "Online" on both devices |
| CSS not loading | Ensure `app/static/css/app.css` exists (run build) |
| Port 80 conflict | `tailscale serve --bg 8000` handles this internally |

7. Nightly Backup
#### Setup
- Ensure backup.py and backup.bat exist in project root
- Test manually: backup.bat → check backups/backup.log
- Schedule in Windows Task Scheduler:
- Task Scheduler (taskschd.msc) → Create Basic Task
- Trigger: Daily, 2:00 AM
- Action: Start a program
- Program: path\to\backup.bat
- Start in: path\to\project\root
#### Behavior
- Creates backups/bakery_YYYYMMDD_HHMMSS.db
- Keeps last 7 backups, deletes older
- Logs to backups/backup.log
- Uses SQLite online backup (safe even if DB is in use)
8. Rebuilding CSS
After adding new Tailwind utility classes in templates:
```
cd app\static\css
tailwindcss.exe -i input.css -o app.css --minify   
```

For live rebuild during development:
```
tailwindcss.exe -i input.css -o app.css --minify --watch   
```

9. Running Tests
```
pytest -v   
```
40+ tests covering: product CRUD, customer CRUD + addresses,
order lifecycle, payments, invoices, export, audit log.

10. `.env.example` (updated)

```env
# ============================================================
# House of Desserts — Environment Configuration
# Copy this to .env and fill in your values
# ============================================================

# --- Business Identity ---
APP_NAME=House of Desserts
APP_TAGLINE=Artisan Bakes & Cakes
FSSAI_NUMBER=
GSTIN=
PHONE=
ADDRESS=
CURRENCY=₹
EMAIL=

# --- Application ---
DEBUG=true
SECRET_KEY=change-me-to-a-random-string
DB_URL=sqlite:///data/bakery.db

# --- Printer (leave PRINTER_TYPE=file to skip printing) ---
PRINTER_TYPE=file
PRINTER_DEVICE=
PRINTER_WIDTH=80

# --- Backup ---
BACKUP_DIR=./backups

# --- Invoice Numbering ---
INVOICE_PREFIX=HOD
INVOICE_START_NUMBER=1
```

