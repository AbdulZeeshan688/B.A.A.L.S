"""Dialogue data model: branches, topics and fact-gated options."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .conditions import ConditionContext, check, validate_condition

EFFECT_KEYS = frozenset({"learn", "give_item", "take_item", "set_flag", "trust", "goto", "visible"})


@dataclass(frozen=True)
class Branch:
    """One possible outcome: shown if `cond` passes; applies `effects`."""

    cond: dict[str, Any] | None
    text: str
    effects: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class Topic:
    """A dialogue option. `requires` decides whether it is offered at all."""

    id: str
    label: str
    requires: dict[str, Any] | None
    replies: tuple[Branch, ...]

    @property
    def from_notes(self) -> bool:
        """True if this option exists because of something the player learned."""
        return bool(self.requires and (self.requires.get("facts") or self.requires.get("items")))


@dataclass(frozen=True)
class NpcDialogue:
    """Greeting branches plus topics for one NPC."""

    greeting: tuple[Branch, ...]
    topics: tuple[Topic, ...]


def pick(branches: tuple[Branch, ...], ctx: ConditionContext, speaker: str | None) -> Branch | None:
    """First branch whose condition passes."""
    for branch in branches:
        if check(branch.cond, ctx, speaker):
            return branch
    return None


def available_topics(dialogue: NpcDialogue, ctx: ConditionContext, speaker: str) -> list[Topic]:
    """Topics currently offered to the player."""
    return [t for t in dialogue.topics if check(t.requires, ctx, speaker)]


def parse_branches(raw: Any, where: str, problems: list[str]) -> tuple[Branch, ...]:
    """Parse a list of branch dicts, collecting problems instead of raising."""
    if not isinstance(raw, list) or not raw:
        problems.append(f"{where}: must be a non-empty list")
        return ()
    branches = []
    for i, item in enumerate(raw):
        spot = f"{where}[{i}]"
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            problems.append(f"{spot}: needs a 'text' string")
            continue
        problems.extend(validate_condition(item.get("if"), spot))
        effects = item.get("effects", [])
        if not isinstance(effects, list):
            problems.append(f"{spot}: 'effects' must be a list")
            effects = []
        for effect in effects:
            if not isinstance(effect, dict) or len(effect) != 1 or next(iter(effect)) not in EFFECT_KEYS:
                problems.append(f"{spot}: bad effect {effect!r}")
        branches.append(Branch(item.get("if"), item["text"], tuple(effects)))
    return tuple(branches)


def parse_dialogue(raw: Any, where: str, problems: list[str]) -> NpcDialogue:
    """Parse one NPC's dialogue block."""
    if not isinstance(raw, dict):
        problems.append(f"{where}: must be an object")
        return NpcDialogue((), ())
    greeting = parse_branches(raw.get("greeting"), f"{where}.greeting", problems)
    topics = []
    for i, t in enumerate(raw.get("topics", [])):
        spot = f"{where}.topics[{i}]"
        if not isinstance(t, dict) or not t.get("id") or not t.get("label"):
            problems.append(f"{spot}: needs 'id' and 'label'")
            continue
        problems.extend(validate_condition(t.get("requires"), spot))
        replies = parse_branches(t.get("replies"), f"{spot}.replies", problems)
        topics.append(Topic(t["id"], t["label"], t.get("requires"), replies))
    return NpcDialogue(greeting, tuple(topics))
