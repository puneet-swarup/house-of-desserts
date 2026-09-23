"""
Nightly database backup.
Run by Windows Task Scheduler at 2 AM daily.
Keeps last 7 backups, deletes older ones.
"""

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

# Paths
DB_PATH = Path(__file__).parent / "data" / "bakery.db"
BACKUP_DIR = Path(__file__).parent / "backups"
LOG_FILE = Path(__file__).parent / "backups" / "backup.log"

# Ensure backup dir exists
BACKUP_DIR.mkdir(exist_ok=True)

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")

def main():
    if not DB_PATH.exists():
        log(f"ERROR: Database not found at {DB_PATH}")
        return

    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"bakery_{timestamp}.db"

    try:
        # SQLite online backup (safe even if DB is in use)
        src = sqlite3.connect(str(DB_PATH))
        dst = sqlite3.connect(str(backup_file))
        with dst:
            src.backup(dst)
        dst.close()
        src.close()

        size_kb = backup_file.stat().st_size / 1024
        log(f"SUCCESS: Backup created → {backup_file.name} ({size_kb:.1f} KB)")

        # Keep only last 7 backups
        backups = sorted(BACKUP_DIR.glob("bakery_*.db"))
        if len(backups) > 7:
            for old in backups[:-7]:
                old.unlink()
                log(f"CLEANUP: Removed old backup {old.name}")

    except Exception as e:
        log(f"ERROR: {e}")

if __name__ == "__main__":
    main()