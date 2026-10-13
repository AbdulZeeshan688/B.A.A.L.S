"""Townspeople: static definitions, per-loop state and schedule following."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .clock import TICK_MINUTES
from .rng import GameRng
from .world import Pos, World

GONE = "gone"


@dataclass(frozen=True)
class ScheduleEntry:
    """From `tick` on, the NPC heads to `place` (or leaves town if place == 'gone')."""

    tick: int
    place: str
    slot: int = 0
    text: str = ""


@dataclass(frozen=True)
class Wander:
    """Cycle through places every `every_ticks`, picking a random spot each time."""

    start_tick: int
    every_ticks: int
    places: tuple[str, ...]


@dataclass(frozen=True)
class NpcDef:
    """Everything about an NPC that never changes."""

    id: str
    letter: str
    name: str
    role: str
    color: str = "white"
    speed: int = 1
    schedule: tuple[ScheduleEntry, ...] = ()
    wander: Wander | None = None
    start_place: str = ""
    start_slot: int = 0


@dataclass
class NpcState:
    """Everything about an NPC that resets each loop."""

    pos: Pos
    present: bool = True
    trust: int = 50
    talks: int = 0
    rumours: dict[str, int] = field(default_factory=dict)
    goto: str | None = None
    wander_picks: dict[int, Pos] = field(default_factory=dict)
    target: Pos | None = None
    paused: int = 0

    def snapshot(self) -> dict:
        """Plain-data view, used for determinism checks and debugging."""
        return {
            "pos": list(self.pos), "present": self.present, "trust": self.trust,
            "talks": self.talks, "rumours": dict(sorted(self.rumours.items())), "goto": self.goto,
        }


def start_position(npc: NpcDef, world: World) -> Pos:
    """Where an NPC stands at 08:00."""
    if npc.start_place:
        return world.region(npc.start_place).spot(npc.start_slot)
    first = npc.schedule[0]
    return world.region(first.place).spot(first.slot)


def scheduled_entry(npc: NpcDef, tick: int) -> ScheduleEntry | None:
    """The latest schedule entry that has started by `tick`."""
    current = None
    for entry in npc.schedule:
        if entry.tick <= tick:
            current = entry
    return current


def wander_target(npc: NpcDef, state: NpcState, tick: int, world: World, rng: GameRng) -> Pos | None:
    """Target tile for wandering NPCs; spots are picked lazily with the loop RNG."""
    wander = npc.wander
    if wander is None or tick < wander.start_tick:
        return None
    cycle = (tick - wander.start_tick) // wander.every_ticks
    if cycle not in state.wander_picks:
        region = world.region(wander.places[cycle % len(wander.places)])
        state.wander_picks[cycle] = rng.choice(region.spots) if region.spots else region.spot(0)
    return state.wander_picks[cycle]


def npc_passable(world: World) -> Callable[[Pos], bool]:
    """NPCs walk on floor and through open doors ('D'), never through 'x'."""
    def passable(pos: Pos) -> bool:
        return world.is_floor(pos) or world.char(pos) == "D"
    return passable


def minutes_to_ticks(minutes: int) -> int:
    """Convert a minute count from data files to ticks."""
    return max(1, minutes // TICK_MINUTES)
