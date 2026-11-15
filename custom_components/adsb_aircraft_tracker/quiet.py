"""Quiet hours and snooze: when an alert should stay silent.

Pure Python (no Home Assistant imports) so it can be exercised standalone.
"""
from __future__ import annotations

from datetime import time


def parse_time(value: object) -> time | None:
    """A time of day from "22:00", "22:00:00" or a time; None if unreadable."""
    if isinstance(value, time):
        return value
    try:
        parts = [int(part) for part in str(value).strip().split(":")]
        return time(*parts[:3]) if 2 <= len(parts) <= 3 else None
    except (TypeError, ValueError):
        return None


def in_window(now: time, start: time | None, end: time | None) -> bool:
    """True when `now` is inside start..end; the window may run past midnight.

    The start is inside, the end is not. A missing time, or start == end,
    is no window at all.
    """
    if start is None or end is None or start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def duration_text(minutes: int) -> str:
    """90 -> "1 h 30 min", 60 -> "1 h", 45 -> "45 min"."""
    hours, rest = divmod(int(minutes), 60)
    if hours and rest:
        return f"{hours} h {rest} min"
    return f"{hours} h" if hours else f"{rest} min"
