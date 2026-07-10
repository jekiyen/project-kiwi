"""Display timezone for the whole app.

Storage stays UTC (naive datetimes in SQLite, as everywhere else in this
codebase) — that's the one place UTC is explicitly required. Everything a
human actually reads — API timestamps, log lines, Telegram messages,
scheduled job wall-clock time — renders in Asia/Jakarta (GMT+7, no DST).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

APP_TZ = ZoneInfo("Asia/Jakarta")
APP_TZ_LABEL = "WIB"


def now_local() -> datetime:
    """Current time, timezone-aware, in Asia/Jakarta."""
    return datetime.now(APP_TZ)


def to_local(dt: datetime) -> datetime:
    """Convert a datetime for display. Naive datetimes are assumed UTC (our storage convention)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(APP_TZ)


def format_local(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a datetime for display in Asia/Jakarta, with an explicit WIB suffix."""
    return f"{to_local(dt).strftime(fmt)} {APP_TZ_LABEL}"
