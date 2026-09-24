# Operations Guide

## Backup

### Manual

```powershell
python -c "import sqlite3; src=sqlite3.connect('data/bakery.db'); dst=sqlite3.connect('backups/bakery-manual.db'); src.backup(dst); dst.close(); src.close()"
```

**Never** `Copy-Item data\bakery.db`. A file copy during a write produces a corrupt backup. Always use SQLite's `.backup` API.

### Scheduled (Windows Task Scheduler)

1. Create `scripts\backup.py`:

   ```python
   import sqlite3
   from datetime import datetime
   from pathlib import Path

   src_path = Path("data/bakery.db")
   out_dir = Path("backups")
   out_dir.mkdir(exist_ok=True)

   stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
   out_path = out_dir / f"bakery-{stamp}.db"

   src = sqlite3.connect(str(src_path))
   dst = sqlite3.connect(str(out_path))
   try:
       src.backup(dst)
   finally:
       dst.close()
       src.close()

   print(f"Backed up to {out_path}")
   ```

2. In Task Scheduler, create a daily task:
   - Program: `D:\puneet\Projects\house-of-desserts\.venv\Scripts\python.exe`
   - Arguments: `scripts\backup.py`
   - Start in: `D:\puneet\Projects\house-of-desserts`

3. Keep 30 days; delete older backups with a second task or a `.bat` that runs `forfiles`.

## Restore

```powershell
# Stop the app first.
Remove-Item data\bakery.db
Remove-Item data\bakery.db-wal -ErrorAction SilentlyContinue
Remove-Item data\bakery.db-shm -ErrorAction SilentlyContinue

Copy-Item backups\bakery-YYYYMMDD-HHMMSS.db data\bakery.db

# Start the app; it will validate the schema on boot.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Always test a restore once per month.** A backup you've never restored is a hope, not a backup.

## Deploy (home network)

Uvicorn binds to `127.0.0.1` by default. To expose on your LAN:

```bash
BIND_HOST=0.0.0.0
BIND_PORT=8000
```

Then:

```powershell
python -m uvicorn app.main:app --host $env:BIND_HOST --port $env:BIND_PORT
```

**Do not expose this to the public internet without auth.** There is no login. If you need remote access, use Tailscale and ACLs.

## Tailscale

1. Install Tailscale on the mini PC and on your phone.
2. Set `BIND_HOST=0.0.0.0` so Tailscale can reach it.
3. From the phone, browse to `http://<tailscale-hostname>:8000`.
4. In the Tailscale admin console, restrict which devices can reach port 8000.
5. **Do not enable Funnel.** That would expose the app to the public internet with no authentication.

## Thermal printer

### File mode (for testing without a printer)

```bash
PRINTER_TYPE=file
```

Prints land in `data/receipt_preview.bin`. Not human-readable — that's ESC/POS binary.

### USB

```bash
PRINTER_TYPE=usb
PRINTER_DEVICE=0x0416:0x5011     # vendor:product in hex
PRINTER_WIDTH=80
```

Find the vendor/product ID in Windows Device Manager → printer → Details → Hardware IDs. The app calls `Usb(vendor, product)` directly.

### Network (LAN/WiFi printer)

```bash
PRINTER_TYPE=network
PRINTER_DEVICE=192.168.1.50:9100
PRINTER_WIDTH=80
```

Verify the printer is listening:

```powershell
Test-NetConnection -ComputerName 192.168.1.50 -Port 9100
```

## Troubleshooting

### "No time zone found with key Asia/Kolkata"

Install `tzdata`:

```powershell
pip install tzdata
```

Windows has no system tz database. On Linux servers this is usually provided by the OS.

### "database is locked"

Three causes:

1. A backup is running while a write is in flight — the `busy_timeout=5000` PRAGMA handles this.
2. Two instances of the app running — kill one.
3. Long-running query holding a lock — check the dashboard's slowest query.

Confirm PRAGMAs are on:

```powershell
python -c "from app.database import engine; from sqlalchemy import text; c=engine.connect(); print(c.execute(text('PRAGMA foreign_keys')).scalar(), c.execute(text('PRAGMA journal_mode')).scalar())"
```

Expect: `1 wal`

### "Advance cannot exceed order total"

Business rule. If a customer wants to pay more than the order total upfront, split into two orders or record the excess as a separate payment after the order is created.

### "Illegal transition: PAID → INQUIRY"

The state machine is enforced. Legal transitions are in `app/models/order.py::ALLOWED_TRANSITIONS`. If you need a "reopen" operation, add a new status (`REFUNDED`) rather than reversing.

### Invoice shows old customer details

That's the snapshot working as designed. The invoice is immutable. If the customer's details changed after invoicing, create a new invoice (VOID the old one first — not yet implemented).

### Duplicate order numbers

Should be impossible — `order_number` has a unique constraint, and the service retries once on collision. If you see it, the constraint is missing. Check:

```powershell
python -c "from sqlalchemy import inspect; from app.database import engine; print([u['column_names'] for u in inspect(engine).get_unique_constraints('orders')])"
```

### Where are the invoices?

`data/invoices/HOD-YYYY-NNNN.pdf`.

### Where are the receipts?

`data/receipt_preview.bin` (file mode only).

### Where are backups?

`backups/` by default. Change `BACKUP_DIR` in `.env`.