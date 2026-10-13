"""Data-driven conditions used by dialogue, objects and doors.

A condition is a dict like {"facts": ["gauge_reading"], "after": "11:00"}.
All keys must hold for the condition to pass. Unknown keys are rejected
when content loads, so typos in data files fail loudly and early.
"""

from __future__ import annotations

from typing import Any, Protocol

from .clock import hhmm_to_tick


class ConditionContext(Protocol):
    """What a condition can ask about the game."""

    tick: int

    def knows(self, fact_id: str) -> bool: ...
    def has_item(self, item: str) -> bool: ...
    def has_flag(self, flag: str) -> bool: ...
    def place_of(self, npc_id: str | None) -> str | None: ...
    def trust_of(self, npc_id: str | None) -> int: ...
    def has_rumour(self, npc_id: str | None, rumour: str) -> bool: ...
    def npc_gone(self, npc_id: str) -> bool: ...


CONDITION_KEYS = frozenset({
    "facts", "no_facts", "items", "no_items", "flags", "no_flags",
    "after", "before", "place", "min_trust", "max_trust",
    "rumour", "no_rumour", "npc_at", "npc_gone",
})


def validate_condition(cond: Any, where: str) -> list[str]:
    """Return a list of problems with a condition dict (empty = valid)."""
    if cond is None:
        return []
    if not isinstance(cond, dict):
        return [f"{where}: condition must be an object"]
    problems = [f"{where}: unknown condition '{k}'" for k in cond if k not in CONDITION_KEYS]
    for key in ("after", "before"):
        if key in cond:
            try:
                hhmm_to_tick(cond[key])
            except (ValueError, TypeError):
                problems.append(f"{where}: bad time for '{key}': {cond[key]!r}")
    for key in ("facts", "no_facts", "items", "no_items", "flags", "no_flags"):
        if key in cond and not isinstance(cond[key], list):
            problems.append(f"{where}: '{key}' must be a list")
    if "npc_at" in cond and not (isinstance(cond["npc_at"], list) and len(cond["npc_at"]) == 2):
        problems.append(f"{where}: 'npc_at' must be [npc, place]")
    return problems


def check(cond: dict[str, Any] | None, ctx: ConditionContext, speaker: str | None = None) -> bool:
    """True if every clause of cond holds. `speaker` is the NPC being talked to."""
    if not cond:
        return True
    tests = (
        all(ctx.knows(f) for f in cond.get("facts", ())),
        not any(ctx.knows(f) for f in cond.get("no_facts", ())),
        all(ctx.has_item(i) for i in cond.get("items", ())),
        not any(ctx.has_item(i) for i in cond.get("no_items", ())),
        all(ctx.has_flag(f) for f in cond.get("flags", ())),
        not any(ctx.has_flag(f) for f in cond.get("no_flags", ())),
        "after" not in cond or ctx.tick >= hhmm_to_tick(cond["after"]),
        "before" not in cond or ctx.tick < hhmm_to_tick(cond["before"]),
        "place" not in cond or ctx.place_of(speaker) == cond["place"],
        "min_trust" not in cond or ctx.trust_of(speaker) >= cond["min_trust"],
        "max_trust" not in cond or ctx.trust_of(speaker) <= cond["max_trust"],
        "rumour" not in cond or ctx.has_rumour(speaker, cond["rumour"]),
        "no_rumour" not in cond or not ctx.has_rumour(speaker, cond["no_rumour"]),
        "npc_at" not in cond or ctx.place_of(cond["npc_at"][0]) == cond["npc_at"][1],
        "npc_gone" not in cond or ctx.npc_gone(cond["npc_gone"]),
    )
    return all(tests)
