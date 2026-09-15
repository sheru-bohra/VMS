"""Timezone-aware date boundaries for location-scoped operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Kolkata"


def resolve_timezone(tz_name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_TIMEZONE)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def get_location_day_bounds(tz_name: Optional[str], reference: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Return UTC start (inclusive) and end (exclusive) for the local calendar day.
    """
    tz = resolve_timezone(tz_name)
    ref = reference or datetime.now(timezone.utc)
    local = ref.astimezone(tz)
    start_local = datetime(local.year, local.month, local.day, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
