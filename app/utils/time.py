"""
Timezone helpers.

Policy: store naive UTC in the database. Convert to the business
timezone (from Settings.business_timezone) only at display or query
boundaries. This is the standard pattern for SQLite + FastAPI apps.

SQLite has no native timezone-aware datetime, so storing aware
datetimes would silently strip the tzinfo on read. Naive UTC is
unambiguous and portable.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def utcnow() -> datetime:
    """Naive UTC now, for storage in SQLite."""
    return datetime.now(UTC).replace(tzinfo=None)


def to_business_tz(dt: datetime | None) -> datetime | None:
    """Convert a stored naive-UTC datetime to business tz for display."""
    if dt is None:
        return None
    settings = get_settings()
    return dt.replace(tzinfo=UTC).astimezone(ZoneInfo(settings.business_timezone))


def business_today_bounds_utc() -> tuple[datetime, datetime]:
    """
    Return (start_utc, end_utc) for "today" in the business timezone,
    expressed as naive UTC datetimes suitable for DB filters.
    """
    settings = get_settings()
    tz = ZoneInfo(settings.business_timezone)
    local_now = datetime.now(tz)
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    local_end = local_start.replace(hour=23, minute=59, second=59, microsecond=999999)
    return (
        local_start.astimezone(UTC).replace(tzinfo=None),
        local_end.astimezone(UTC).replace(tzinfo=None),
    )


def business_day_bounds_utc(date_str: str) -> tuple[datetime, datetime]:
    """
    Given 'YYYY-MM-DD' interpreted in the business timezone, return
    the [start, end] UTC range for filtering.
    """
    settings = get_settings()
    tz = ZoneInfo(settings.business_timezone)
    local_start = datetime.fromisoformat(date_str).replace(
        tzinfo=tz, hour=0, minute=0, second=0, microsecond=0
    )
    local_end = local_start.replace(hour=23, minute=59, second=59, microsecond=999999)
    return (
        local_start.astimezone(UTC).replace(tzinfo=None),
        local_end.astimezone(UTC).replace(tzinfo=None),
    )
