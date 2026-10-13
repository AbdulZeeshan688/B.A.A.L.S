"""Loop rules: what resets at 08:00, and how a loop can end."""

from __future__ import annotations

from .content import Content
from .knowledge import Notebook
from .npc import NpcState, start_position
from .state import GameState, Outcome, Player, Stats


def fresh_npcs(content: Content) -> dict[str, NpcState]:
    """Every NPC back at their 08:00 spot with default trust."""
    return {n.id: NpcState(pos=start_position(n, content.world)) for n in content.npcs}


def new_state(content: Content, seed: int, notebook: Notebook | None = None,
              loop: int = 1, stats: Stats | None = None) -> GameState:
    """State at 08:00 of `loop`, keeping a notebook and stats if given."""
    return GameState(seed=seed, loop=loop, tick=0, player=Player(pos=content.start),
                     npcs=fresh_npcs(content), notebook=notebook or Notebook(), stats=stats or Stats())


def reset_for_next_loop(state: GameState, content: Content) -> None:
    """Record the outcome, then rewind the world. Notebook and stats survive."""
    if state.outcome is not None:
        state.stats.outcomes.append(state.outcome.symbol)
    state.ghost = list(state.player.trail)
    state.loop += 1
    state.tick = 0
    state.player = Player(pos=content.start)
    state.npcs = fresh_npcs(content)
    state.flags = set()
    state.outcome = None
    state.events = []
    state.fired = set()
    state.used_topics = set()


def is_win(state: GameState, content: Content) -> bool:
    """True if the win rule is met right now."""
    rule = content.win
    npc = state.npcs.get(rule.npc)
    if npc is None or not npc.present or rule.flag not in state.flags:
        return False
    region = content.world.region_at(npc.pos)
    return region is not None and region.id == rule.place and state.tick <= rule.before_tick


def ended(state: GameState) -> bool:
    """True if the loop is over (any outcome)."""
    return state.outcome is not None


__all__ = ["Outcome", "new_state", "reset_for_next_loop", "is_win", "ended", "fresh_npcs"]
