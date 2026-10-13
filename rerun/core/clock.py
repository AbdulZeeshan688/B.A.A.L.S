"""Game time: ticks <-> clock strings. One loop runs 08:00-14:00."""

from __future__ import annotations

import re

TICK_MINUTES = 2
DAY_START = 8 * 60
DAY_END = 14 * 60
DAY_TICKS = (DAY_END - DAY_START) // TICK_MINUTES

_TIME_RE = re.compile(r"^\s*(\d{1,2})\s*[:.h]?\s*(\d{2})\s*$")


def tick_to_minutes(tick: int) -> int:
    """Minutes since midnight for a tick."""
    return DAY_START + tick * TICK_MINUTES


def format_minutes(minutes: int) -> str:
    """Format minutes since midnight as HH:MM."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def tick_to_hhmm(tick: int) -> str:
    """Clock string (HH:MM) for a tick."""
    return format_minutes(tick_to_minutes(tick))


def parse_hhmm(text: str) -> int:
    """Parse 'HH:MM' (also '0930', '9.30') to minutes since midnight.

    Raises ValueError with a player-friendly message on bad input.
    """
    match = _TIME_RE.match(text or "")
    if not match:
        raise ValueError(f"'{text.strip()}' is not a time. Try something like 09:30.")
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        raise ValueError(f"{hours:02d}:{minutes:02d} is not a real time.")
    return hours * 60 + minutes


def hhmm_to_tick(text: str) -> int:
    """Convert a clock string to the first tick at or after that time.

    Raises ValueError if the time is not inside the 08:00-14:00 loop.
    """
    minutes = parse_hhmm(text)
    if minutes < DAY_START or minutes > DAY_END:
        raise ValueError(f"The day only runs {format_minutes(DAY_START)}-{format_minutes(DAY_END)}.")
    return -(-(minutes - DAY_START) // TICK_MINUTES)


def duration_text(minutes: int) -> str:
    """Human duration like '4h 18m'."""
    hours, mins = divmod(max(0, minutes), 60)
    return f"{hours}h {mins:02d}m" if hours else f"{mins}m"


def time_left_text(tick: int) -> str:
    """Time left until the flood, e.g. '4h 18m'."""
    return duration_text((DAY_TICKS - tick) * TICK_MINUTES)
