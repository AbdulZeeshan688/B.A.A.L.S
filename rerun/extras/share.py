"""Spoiler-free share line, like Wordle results."""

from __future__ import annotations

from datetime import date

from ..core.clock import TICK_MINUTES, duration_text

DAILY_MIN, DAILY_MAX = 2000_01_01, 2999_12_31


def daily_seed(day: date | None = None) -> int:
    """Seed for the daily challenge: the date as YYYYMMDD, identical for every player."""
    return int((day or date.today()).strftime("%Y%m%d"))


def run_id(seed: int) -> str:
    """Short public id for a seed ('Daily 2026-10-14' for daily seeds)."""
    if DAILY_MIN <= seed <= DAILY_MAX:
        return f"Daily {seed // 10000}-{seed // 100 % 100:02d}-{seed % 100:02d}"
    return f"#{seed % 10000:04d}"


def share_line(seed: int, outcomes: list[str]) -> str:
    """e.g. 'RERUN #4821  SAVED in 4 loops  ~~^*'. Encodes outcomes only, never the solution."""
    loops = len(outcomes)
    status = "SAVED" if outcomes and outcomes[-1] == "*" else "FLOODED"
    plural = "loop" if loops == 1 else "loops"
    return f"RERUN {run_id(seed)}  {status} in {loops} {plural}  {''.join(outcomes)}"


def time_used_text(ticks: int) -> str:
    """Total in-game time across all loops."""
    return duration_text(ticks * TICK_MINUTES)
