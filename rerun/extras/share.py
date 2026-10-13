"""Spoiler-free share line, like Wordle results."""

from __future__ import annotations

from ..core.clock import TICK_MINUTES, duration_text


def run_id(seed: int) -> str:
    """Short public id for a seed."""
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
