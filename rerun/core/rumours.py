"""Rumours: who saw what, and how gossip spreads between NPCs."""

from __future__ import annotations

from typing import Callable

from .content import Content
from .rng import GameRng
from .state import Event, GameState
from .world import Pos, chebyshev


def witnesses(state: GameState, content: Content, at: Pos, radius: int, need_sight: bool) -> list[str]:
    """NPC ids close enough (and with line of sight, if required) to notice something at `at`."""
    seen = []
    for npc in content.npcs:
        st = state.npcs[npc.id]
        if not st.present or chebyshev(st.pos, at) > radius:
            continue
        if need_sight and not content.world.line_of_sight(st.pos, at):
            continue
        seen.append(npc.id)
    return seen


def plant(state: GameState, npc_id: str, rumour: str) -> bool:
    """Give an NPC a rumour about the player. Returns True if it was new to them."""
    st = state.npcs[npc_id]
    if rumour in st.rumours:
        return False
    st.rumours[rumour] = state.tick
    return True


def spread(state: GameState, content: Content, rng: GameRng, in_view: Callable[[Pos], bool]) -> list[Event]:
    """One tick of gossip: neighbours share each rumour with a seeded chance."""
    events = []
    present = [n.id for n in content.npcs if state.npcs[n.id].present]
    for i, a in enumerate(present):
        for b in present[i + 1:]:
            sa, sb = state.npcs[a], state.npcs[b]
            if chebyshev(sa.pos, sb.pos) > 1:
                continue
            for src, dst, dst_state in ((a, b, sb), (b, a, sa)):
                for rumour in sorted(state.npcs[src].rumours):
                    if rumour in dst_state.rumours or not rng.chance(content.rules.spread_chance):
                        continue
                    plant(state, dst, rumour)
                    if in_view(sa.pos) or in_view(sb.pos):
                        events.append(Event(f"{content.npc(src).name} whispers something to "
                                            f"{content.npc(dst).name}.", "rumour"))
    return events
