#!/usr/bin/env python3
"""
Nightly backup for House of Desserts.

Backs up ~/hod-data/ to ~/hod-backups/YYYY-MM-DD/:
  - bakery.db   via SQLite's .backup() API (safe during writes)
  - everything else via plain file copy (invoices, reports)

Reads DB_URL and BACKUP_DIR from .env.
Prunes backups older than --retention-days (default 30).

Exit codes:
  0  success
  1  unexpected error
  2  configuration or source-missing error
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


def load_env(env_path: Path) -> dict[str, str]:
    """Minimal .env reader — no python-dotenv dependency."""
    if not env_path.exists():
        print(f"ERROR: .env not found at {env_path}", file=sys.stderr)
        sys.exit(2)
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        values[k.strip()] = v.strip()
    return values


def parse_sqlite_path(db_url: str) -> Path:
    """Extract filesystem path from a SQLAlchemy sqlite:// URL.

    sqlite:////abs/path.db    -> /abs/path.db
    sqlite:///rel/path.db     -> rel/path.db
    """
    m = re.match(r"^sqlite:///(.+)$", db_url)
    if not m:
        print(f"ERROR: not a sqlite URL: {db_url}", file=sys.stderr)
        sys.exit(2)
    raw = m.group(1)
    return Path(raw)


def backup_sqlite(src: Path, dest: Path) -> None:
    """Copy a SQLite DB using the online backup API."""
    if not src.exists():
        raise FileNotFoundError(f"Source DB not found: {src}")
    src_conn = sqlite3.connect(str(src))
    try:
        dest_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()


def copy_tree(src: Path, dest: Path, skip: set[str]) -> None:
    """Recursively copy src into dest, skipping any names in `skip`."""
    if not src.exists():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        if entry.name in skip:
            continue
        target = dest / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)


def prune_old(backup_root: Path, retention_days: int) -> list[str]:
    """Delete dated folders older than retention_days. Returns deleted names."""
    cutoff = date.today() - timedelta(days=retention_days)
    removed: list[str] = []
    for entry in sorted(backup_root.iterdir()):
        if not entry.is_dir():
            continue
        try:
            folder_date = datetime.strptime(entry.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if folder_date < cutoff:
            shutil.rmtree(entry)
            removed.append(entry.name)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up HOD data")
    parser.add_argument(
        "--env",
        default=str(Path.home() / "house-of-desserts" / ".env"),
        help="Path to .env file",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Delete backups older than N days (default 30)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print plan, don't write")
    args = parser.parse_args()

    env = load_env(Path(args.env))
    db_path = parse_sqlite_path(env["DB_URL"])
    backup_root = Path(env["BACKUP_DIR"]).resolve()
    data_dir = db_path.parent

    today = date.today().isoformat()
    dest = backup_root / today

    print(f"[{datetime.now().isoformat(timespec='seconds')}] HOD backup")
    print(f"  Source:    {data_dir}")
    print(f"  Backup:    {backup_root}")
    print(f"  Today dir: {dest}")

    if args.dry_run:
        print("  DRY RUN — nothing written")
        return 0

    if not data_dir.exists():
        print(f"ERROR: source dir missing: {data_dir}", file=sys.stderr)
        return 2

    backup_root.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)  # same-day rerun
    dest.mkdir(parents=True)

    print("  bakery.db  (SQLite backup API)")
    backup_sqlite(db_path, dest / db_path.name)

    print("  everything else")
    copy_tree(data_dir, dest, skip={db_path.name})

    removed = prune_old(backup_root, args.retention_days)
    if removed:
        print(f"  pruned: {', '.join(removed)}")

    total = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    print(f"  size: {total / 1024 / 1024:.2f} MB")
    print(f"[{datetime.now().isoformat(timespec='seconds')}] Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
