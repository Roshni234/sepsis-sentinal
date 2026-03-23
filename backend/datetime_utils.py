"""DateTime utilities for backend - ensure consistent IST handling."""

from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+
import json
from typing import Any

IST = ZoneInfo("Asia/Kolkata")


def get_ist_now() -> datetime:
    """Get current time in IST with timezone info."""
    return datetime.now(IST)


def ensure_ist_aware(dt: datetime) -> datetime:
    """Ensure a datetime object is timezone-aware in IST."""
    if dt is None:
        return None

    if dt.tzinfo is None:
        # Assume naive datetime is IST
        return dt.replace(tzinfo=IST)

    # Convert any timezone to IST
    return dt.astimezone(IST)


def datetime_to_iso_string(dt: datetime) -> str:
    """Convert datetime to ISO string (IST)."""
    if dt is None:
        return None

    dt = ensure_ist_aware(dt)
    return dt.isoformat()


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder for datetime objects (IST)."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return datetime_to_iso_string(obj)
        return super().default(obj)
