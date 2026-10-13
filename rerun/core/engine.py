"""The game engine: applies player actions and advances the simulation.

The UI never changes state directly; it calls the methods here. Each
action that costs time calls `_advance()` exactly once per tick, which
moves NPCs, spreads rumours, fires timed events and checks win/flood.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import rumours
from .clock import DAY_TICKS, hhmm_to_tick, tick_to_hhmm
from .conditions import check
from .content import Content, Door
from .dialogue import Topic, available_topics, pick
from .knowledge import Notebook
from .loop import is_win, new_state, reset_for_next_loop
from .npc import GONE, NpcDef, npc_passable, scheduled_entry, wander_target
from .rng import GameRng
from .state import Event, GameState, Outcome, Stats
from .world import Pos, chebyshev


@dataclass(frozen=True)
class Target:
    """Something next to the player that E can interact with."""

    kind: str  # "npc" or "object"
    id: str
    name: str


class Game:
    """One run of the game: a content pack plus a mutable GameState."""

    def __init__(self, content: Content, seed: int, notebook: Notebook | None = None,
                 loop: int = 1, stats: Stats | None = None) -> None:
        self.content = content
        self.world = content.world
        self.state: GameState = new_state(content, seed, notebook, loop, stats)
        self._npc_passable = npc_passable(self.world)
        self._begin_loop()

    # ----------------------------------------------------------- conditions
    @property
    def tick(self) -> int:
        """Current tick of this loop."""
        return self.state.tick

    def knows(self, fact_id: str) -> bool:
        """True if the notebook has this fact."""
        return self.state.notebook.knows(fact_id)

    def has_item(self, item: str) -> bool:
        """True if the player carries this item."""
        return item in self.state.player.items

    def has_flag(self, flag: str) -> bool:
        """True if a per-loop flag is set."""
        return flag in self.state.flags

    def place_of(self, npc_id: str | None) -> str | None:
        """Region id of an NPC (or the player if npc_id is None)."""
        if npc_id is None:
            pos = self.state.player.pos
        else:
            npc = self.state.npcs.get(npc_id)
            if npc is None or not npc.present:
                return None
            pos = npc.pos
        region = self.world.region_at(pos)
        return region.id if region else None

    def trust_of(self, npc_id: str | None) -> int:
        """Trust value of an NPC (50 if unknown)."""
        npc = self.state.npcs.get(npc_id or "")
        return npc.trust if npc else 50

    def has_rumour(self, npc_id: str | None, rumour: str) -> bool:
        """True if the NPC has heard this rumour about the player."""
        npc = self.state.npcs.get(npc_id or "")
        return bool(npc and rumour in npc.rumours)

    def npc_gone(self, npc_id: str) -> bool:
        """True if the NPC has left town this loop."""
        npc = self.state.npcs.get(npc_id)
        return bool(npc and not npc.present)

    # -------------------------------------------------------------- queries
    def clock(self) -> str:
        """Current time as HH:MM."""
        return tick_to_hhmm(self.state.tick)

    def region_name(self, pos: Pos | None = None) -> str:
        """Human name of the region at pos (default: the player)."""
        region = self.world.region_at(pos or self.state.player.pos)
        return region.name if region else self.content.name

    def in_view(self, pos: Pos) -> bool:
        """True if the player can see this tile."""
        me = self.state.player.pos
        return chebyshev(me, pos) <= self.content.rules.view_radius and self.world.line_of_sight(me, pos)

    def visible_npcs(self) -> list[NpcDef]:
        """NPCs the player can currently see."""
        return [n for n in self.content.npcs
                if self.state.npcs[n.id].present and self.in_view(self.state.npcs[n.id].pos)]

    def door_at(self, pos: Pos) -> Door | None:
        """Door definition at a tile, if any."""
        return next((d for d in self.content.doors if d.pos == pos), None)

    def door_open(self, door: Door) -> bool:
        """True if the door currently lets the player in."""
        if door.open_if is not None and not check(door.open_if, self):
            return False
        return not (door.locked_if is not None and check(door.locked_if, self))

    def interactables(self) -> list[Target]:
        """NPCs and objects within reach (adjacent or same tile)."""
        me = self.state.player.pos
        found = [Target("npc", n.id, n.name) for n in self.content.npcs
                 if self.state.npcs[n.id].present and chebyshev(self.state.npcs[n.id].pos, me) <= 1]
        found += [Target("object", o.id, o.name) for o in self.content.objects if chebyshev(o.pos, me) <= 1]
        return found

    def topics(self, npc_id: str) -> list[Topic]:
        """Dialogue options currently offered by an NPC."""
        return available_topics(self.content.dialogue[npc_id], self, npc_id)

    def asked(self, npc_id: str, topic_id: str) -> bool:
        """True if the player already chose this topic this loop."""
        return f"{npc_id}.{topic_id}" in self.state.used_topics

    def current_hint(self) -> str | None:
        """The 'what to try next' line: first hint whose condition matches right now."""
        branch = pick(self.content.hints, self, None)
        return branch.text if branch else None

    def drain_events(self) -> list[Event]:
        """Return and clear pending events for the UI."""
        events, self.state.events = self.state.events, []
        return events

    # -------------------------------------------------------------- actions
    def move(self, dx: int, dy: int) -> bool:
        """Step one tile. Costs a tick only if the step happens."""
        s = self.state
        if s.outcome:
            return False
        dest = (s.player.pos[0] + dx, s.player.pos[1] + dy)
        door = self.door_at(dest)
        if door is not None:
            if not (self.door_open(door) or self.place_of(None) == door.building):
                self._say(door.locked_text)
                return False
        elif not (self.world.is_floor(dest) or self.world.char(dest) == "D"):
            return False
        s.player.pos = dest
        s.player.trail.append(dest)
        if door is not None:
            self._apply(door.on_enter, None)
        self._advance()
        return True

    def wait(self) -> None:
        """Let one tick pass."""
        if not self.state.outcome:
            self._advance()

    def talk(self, npc_id: str) -> str:
        """Open a conversation (1 tick). Returns the greeting."""
        st = self.state.npcs[npc_id]
        self._advance()
        st.talks += 1
        self.state.stats.talks += 1
        rules = self.content.rules
        if st.talks > rules.annoy_after_talks:
            st.trust = max(0, st.trust - rules.annoy_trust_penalty)
            self._say(f"{self.content.npc(npc_id).name} looks tired of you. (trust down)", "warn")
        branch = pick(self.content.dialogue[npc_id].greeting, self, npc_id)
        return branch.text if branch else "..."

    def choose(self, npc_id: str, topic_id: str) -> str:
        """Pick a dialogue option (free). Returns the reply and applies its effects."""
        topic = next((t for t in self.topics(npc_id) if t.id == topic_id), None)
        if topic is None:
            return "They don't follow."
        self.state.used_topics.add(f"{npc_id}.{topic_id}")
        branch = pick(topic.replies, self, npc_id)
        if branch is None:
            return "..."
        self._apply(branch.effects, npc_id)
        self._check_end()
        return branch.text

    def inspect(self, object_id: str) -> str:
        """Use an object (1 tick). Returns what the player sees."""
        obj = next(o for o in self.content.objects if o.id == object_id)
        self._advance()
        if self.state.outcome:
            return ""
        branch = pick(obj.use, self, None)
        if branch is None:
            return f"Nothing special about the {obj.name}."
        self._apply(branch.effects, None)
        self._check_end()
        return branch.text

    def shout(self) -> None:
        """Shout a warning (1 tick). Loud, public, and risky."""
        if self.state.outcome:
            return
        self._say("You shout: \"THE DAM IS GOING TO BREAK!\"", "important")
        heard = rumours.witnesses(self.state, self.content, self.state.player.pos,
                                  self.content.rules.shout_radius, need_sight=False)
        if heard:
            self._spread_word(heard, "panic")
        else:
            self._say("Nobody is close enough to hear you.")
        self._check_end()
        if not self.state.outcome:
            self._advance()

    def skip_to(self, text: str) -> str | None:
        """Advance to a time, stopping early for anything interesting.

        Returns an error message for invalid input, or None on success.
        """
        try:
            target = hhmm_to_tick(text)
        except ValueError as exc:
            return str(exc)
        if target <= self.state.tick:
            return f"It's already {self.clock()}. Time only moves forward (until 14:00)."
        seen = {n.id for n in self.visible_npcs()}
        while self.state.tick < target and not self.state.outcome:
            before = len(self.state.events)
            self._advance()
            if any(e.important for e in self.state.events[before:]):
                break
            now_seen = {n.id for n in self.visible_npcs()}
            arrived = [self.content.npc(i).name for i in sorted(now_seen - seen)]
            if arrived:
                self._say(f"{', '.join(arrived)} comes into view.")
                break
            seen = now_seen
        return None

    def restart_loop(self) -> None:
        """Give up on this loop early."""
        if not self.state.outcome:
            self.state.outcome = Outcome.RESTARTED

    def next_loop(self) -> None:
        """Rewind to 08:00. Only the notebook and stats survive."""
        reset_for_next_loop(self.state, self.content)
        self._begin_loop()

    # ------------------------------------------------------------- internal
    def _begin_loop(self) -> None:
        s = self.state
        self.rng = GameRng(s.seed).for_loop(s.loop)
        s.player.trail = [s.player.pos]
        if s.loop == 1:
            self._say(self.content.intro)
        else:
            self._say(f"08:00. The bus again. Loop {s.loop}. Your notebook is still in your pocket.", "important")

    def _say(self, text: str, kind: str = "info") -> None:
        self.state.events.append(Event(text, kind))

    def _learn(self, fact_id: str) -> None:
        if self.state.notebook.learn(fact_id, self.state.loop):
            self._say(f"Notebook +  {self.content.facts[fact_id].short}", "fact")

    def _apply(self, effects: tuple[dict, ...], speaker: str | None) -> None:
        s = self.state
        for effect in effects:
            key, value = next(iter(effect.items()))
            if key == "learn":
                self._learn(value)
            elif key == "give_item":
                s.player.items.add(value)
            elif key == "take_item":
                s.player.items.discard(value)
            elif key == "set_flag":
                s.flags.add(value)
            elif key == "trust" and speaker:
                npc = s.npcs[speaker]
                npc.trust = max(0, min(100, npc.trust + int(value)))
            elif key == "goto" and speaker:
                s.npcs[speaker].goto = value
            elif key == "visible":
                seen = rumours.witnesses(s, self.content, s.player.pos, self.content.rules.witness_radius, True)
                if seen:
                    self._spread_word(seen, value)

    def _spread_word(self, npc_ids: list[str], rumour: str) -> None:
        """Witnesses get a rumour and trust the player less."""
        penalty = self.content.rules.witness_trust_penalty
        for npc_id in npc_ids:
            rumours.plant(self.state, npc_id, rumour)
            npc = self.state.npcs[npc_id]
            npc.trust = max(0, npc.trust - penalty)
        self.state.stats.rumours_started += 1
        names = ", ".join(self.content.npc(i).name for i in npc_ids)
        self._say(f"{names} saw that. People will talk.", "rumour")

    def _advance(self) -> None:
        s = self.state
        if s.outcome:
            return
        s.tick += 1
        s.stats.ticks_used += 1
        self._move_npcs()
        s.events.extend(rumours.spread(s, self.content, self.rng, self.in_view))
        self._timed_events()
        self._check_end()
        if not s.outcome and s.tick >= DAY_TICKS:
            s.outcome = Outcome.FLOODED
            if self.content.flood_learn:
                self._learn(self.content.flood_learn)

    def _check_end(self) -> None:
        s, rules = self.state, self.content.rules
        if s.outcome:
            return
        if is_win(s, self.content):
            s.outcome = Outcome.SAVED
            s.stats.outcomes.append(Outcome.SAVED.symbol)
            return
        if rules.arrest_npc and self.has_rumour(rules.arrest_npc, rules.arrest_rumour):
            mayor = self.content.npc(rules.arrest_npc).name
            self._say(f"{mayor} heard you were spreading panic. A guard drags you away.", "warn")
            s.outcome = Outcome.ARRESTED

    def _npc_target(self, npc: NpcDef) -> Pos | None:
        st = self.state.npcs[npc.id]
        if st.goto:
            return self.world.region(st.goto).spot(0)
        if npc.wander:
            return wander_target(npc, st, self.state.tick, self.world, self.rng)
        entry = scheduled_entry(npc, self.state.tick)
        if entry is None:
            return st.pos
        if entry.place == GONE:
            return None
        return self.world.region(entry.place).spot(entry.slot)

    def _move_npcs(self) -> None:
        for npc in self.content.npcs:
            st = self.state.npcs[npc.id]
            if not st.present:
                continue
            target = self._npc_target(npc)
            if target is None:
                st.present = False
                entry = scheduled_entry(npc, self.state.tick)
                self._say(entry.text if entry and entry.text else f"{npc.name} has left town.", "important")
                continue
            st.target = target
            dist = self.world.distance_map(target, self._npc_passable, "npc")
            for _ in range(npc.speed):
                st.pos = self.world.step_towards(st.pos, dist)

    def _timed_events(self) -> None:
        s = self.state
        for i, ann in enumerate(self.content.announcements):
            key = f"ann{i}"
            if key in s.fired or s.tick < ann.tick or self.place_of(ann.npc) != ann.place:
                continue
            s.fired.add(key)
            if chebyshev(s.npcs[ann.npc].pos, s.player.pos) <= ann.radius:
                self._say(ann.text, "important")
                self._apply(ann.effects, ann.npc)
        for i, omen in enumerate(self.content.omens):
            key = f"omen{i}"
            if key not in s.fired and s.tick >= omen.tick:
                s.fired.add(key)
                self._say(omen.text)
