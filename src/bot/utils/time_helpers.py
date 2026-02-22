"""Timezone-aware datetime utilities."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def now_in_timezone(timezone_name: str) -> datetime:
    """Return current localized datetime for scheduling and logs."""
    return datetime.now(tz=ZoneInfo(timezone_name))
