"""GameState: every bit of mutable game data in one place."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .knowledge import Notebook
from .npc import NpcState
from .world import Pos


class Outcome(Enum):
    """How a loop ended."""

    FLOODED = "flooded"
    ARRESTED = "arrested"
    RESTARTED = "restarted"
    SAVED = "saved"

    @property
    def symbol(self) -> str:
        """Spoiler-free symbol for the share line."""
        return {"flooded": "~", "arrested": "^", "restarted": "~", "saved": "*"}[self.value]


@dataclass(frozen=True)
class Event:
    """Something the player should be told. `kind` drives colour and skip-stopping."""

    text: str
    kind: str = "info"  # info | fact | rumour | important | warn

    @property
    def important(self) -> bool:
        """Important events interrupt time skipping."""
        return self.kind in ("fact", "rumour", "important", "warn")


@dataclass
class Stats:
    """Totals across all loops of one run."""

    outcomes: list[str] = field(default_factory=list)
    ticks_used: int = 0
    rumours_started: int = 0
    talks: int = 0

    def to_dict(self) -> dict:
        """Serialise for the save file."""
        return {"outcomes": list(self.outcomes), "ticks_used": self.ticks_used,
                "rumours_started": self.rumours_started, "talks": self.talks}

    @classmethod
    def from_dict(cls, data: dict) -> "Stats":
        """Load from save data, tolerating missing or odd values."""
        outcomes = [s for s in data.get("outcomes", []) if s in ("~", "^", "*")]
        return cls(outcomes, int(data.get("ticks_used", 0)), int(data.get("rumours_started", 0)),
                   int(data.get("talks", 0)))


@dataclass
class Player:
    """The player's per-loop state."""

    pos: Pos
    items: set[str] = field(default_factory=set)
    trail: list[Pos] = field(default_factory=list)


@dataclass
class GameState:
    """Everything that changes while playing."""

    seed: int
    loop: int
    tick: int
    player: Player
    npcs: dict[str, NpcState]
    notebook: Notebook
    stats: Stats
    flags: set[str] = field(default_factory=set)
    outcome: Outcome | None = None
    events: list[Event] = field(default_factory=list)
    ghost: list[Pos] = field(default_factory=list)
    fired: set[str] = field(default_factory=set)
    used_topics: set[str] = field(default_factory=set)

    def snapshot(self) -> dict:
        """Deterministic plain-data view of the whole state (for tests and replays)."""
        return {
            "seed": self.seed, "loop": self.loop, "tick": self.tick,
            "player": [list(self.player.pos), sorted(self.player.items)],
            "npcs": {k: v.snapshot() for k, v in sorted(self.npcs.items())},
            "notebook": self.notebook.to_dict(), "stats": self.stats.to_dict(),
            "flags": sorted(self.flags), "outcome": self.outcome.value if self.outcome else None,
        }
