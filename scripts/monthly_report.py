#!/usr/bin/env python3
"""
Generate the previous month's report. Intended to run from cron on the
1st of each month. Can also be called manually with --year/--month.

Usage:
    python scripts/monthly_report.py
    python scripts/monthly_report.py --year 2026 --month 8
    python scripts/monthly_report.py --current     # this month (partial)
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

# Make sure `app` package is importable when run from cron
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.services import reports_service  # noqa: E402


def _previous_month() -> tuple[int, int]:
    today = date.today()
    first = today.replace(day=1)
    last_month_end = first - timedelta(days=1)
    return last_month_end.year, last_month_end.month


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HOD monthly report")
    parser.add_argument("--year", type=int, help="Year (default: previous month)")
    parser.add_argument("--month", type=int, help="Month 1-12 (default: previous month)")
    parser.add_argument(
        "--current",
        action="store_true",
        help="Use the current month instead of the previous month",
    )
    args = parser.parse_args()

    if args.year and args.month:
        year, month = args.year, args.month
    elif args.current:
        today = date.today()
        year, month = today.year, today.month
    else:
        year, month = _previous_month()

    db = SessionLocal()
    try:
        result = reports_service.generate_report(db, year, month)
    finally:
        db.close()

    print(
        f"[{result['period_label']}] "
        f"orders={result['orders_active']} "
        f"revenue={result['total_revenue']} "
        f"pdf={result['pdf_path']} "
        f"csv={result['csv_path']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
