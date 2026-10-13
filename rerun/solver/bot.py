"""Solver bot: plays RERUN through the real app by pressing keys.

It uses exactly the same code path as a human (App.handle_key), only
reading game state to plan where to walk. It proves both winning routes
work, and it records the demo replay used in the pitch.

    python -m rerun.solver.bot --route honest
    python -m rerun.solver.bot --route demo --record demo.rec
"""

from __future__ import annotations

import argparse
import sys
from collections import deque
from pathlib import Path

from ..app import App, Options
from ..core import rumours
from ..core.clock import DAY_TICKS, hhmm_to_tick, tick_to_hhmm
from ..core.content import Content, load_content
from ..core.engine import Game
from ..core.world import NEIGHBOURS, Pos, chebyshev
from ..persistence.save import SaveStore
from ..ui import keys as K
from ..ui.keys import KeyEvent, char_key
from ..ui.screens.dialogue import ChooserScreen, DialogueScreen
from ..ui.screens.endings import LoopEndScreen, WinScreen
from ..ui.terminal import HeadlessIO
from ..ui.theme import Theme

DIRS = {(0, -1): K.UP, (0, 1): K.DOWN, (-1, 0): K.LEFT, (1, 0): K.RIGHT}
MAX_KEYS = 20_000


class BotStuck(RuntimeError):
    """The bot could not do what its script asked."""


class Bot:
    """Drives a headless App with key presses."""

    def __init__(self, seed: int = 1, content: Content | None = None, record: Path | None = None) -> None:
        options = Options(new=True, seed=seed, reduced_motion=True, record=record)
        self.app = App(options, HeadlessIO(), SaveStore(enabled=False), Theme(), content or load_content())
        self.app.start()
        if record is None:
            self.app.new_game(seed)
        self.presses = 0

    # --------------------------------------------------------------- basics
    @property
    def game(self) -> Game:
        """The game being played."""
        return self.app.game

    @property
    def screen(self):
        """The top screen."""
        return self.app.stack[-1]

    def press(self, key: KeyEvent) -> None:
        """Press one key through the real input path."""
        self.presses += 1
        if self.presses > MAX_KEYS:
            raise BotStuck("too many key presses")
        self.app.handle_key(key)

    def type_text(self, text: str) -> None:
        """Type characters then Enter."""
        for ch in text:
            self.press(char_key(ch))
        self.press(KeyEvent(K.ENTER))

    @property
    def over(self) -> bool:
        """True if the loop has ended (any outcome)."""
        return self.game.state.outcome is not None

    # ------------------------------------------------------------ movement
    def _passable(self, pos: Pos) -> bool:
        game = self.game
        door = game.door_at(pos)
        if door is not None:
            return game.door_open(door) or game.place_of(None) == door.building
        return game.world.is_floor(pos) or game.world.char(pos) == "D"

    def _path(self, goal_test) -> list[Pos]:
        start = self.game.state.player.pos
        prev: dict[Pos, Pos | None] = {start: None}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            if goal_test(cur):
                path = []
                while cur != start:
                    path.append(cur)
                    cur = prev[cur]
                return path[::-1]
            for dx, dy in NEIGHBOURS:
                nxt = (cur[0] + dx, cur[1] + dy)
                if nxt not in prev and self.game.world.in_bounds(nxt) and self._passable(nxt):
                    prev[nxt] = cur
                    queue.append(nxt)
        raise BotStuck(f"no path from {start}")

    def _step(self, nxt: Pos) -> None:
        me = self.game.state.player.pos
        self.press(KeyEvent(DIRS[(nxt[0] - me[0], nxt[1] - me[1])]))

    def walk_to(self, target: Pos) -> None:
        """Walk until standing on target."""
        while self.game.state.player.pos != target and not self.over:
            self._step(self._path(lambda p: p == target)[0])

    def walk_next_to(self, target: Pos) -> None:
        """Walk until adjacent to a fixed tile (e.g. an object)."""
        while chebyshev(self.game.state.player.pos, target) > 1 and not self.over:
            self._step(self._path(lambda p: chebyshev(p, target) <= 1)[0])

    def chase(self, npc_id: str) -> None:
        """Walk until next to a (possibly moving) NPC."""
        for _ in range(DAY_TICKS):
            st = self.game.state.npcs[npc_id]
            if self.over or not st.present:
                break
            if chebyshev(self.game.state.player.pos, st.pos) <= 1:
                return
            try:
                self._step(self._path(lambda p, t=st.pos: chebyshev(p, t) <= 1)[0])
            except BotStuck:
                self.press(char_key("."))  # they're behind a locked door; wait for them
        if not self.over:
            raise BotStuck(f"could not reach {npc_id}")

    # --------------------------------------------------------------- time
    def wait_until(self, hhmm: str) -> None:
        """Skip time with the T prompt (repeating if it stops early)."""
        target = hhmm_to_tick(hhmm)
        while self.game.state.tick < target and not self.over:
            self.press(char_key("t"))
            self.type_text(hhmm)

    def wait_ticks(self, n: int) -> None:
        """Press '.' n times."""
        for _ in range(n):
            if self.over:
                return
            self.press(char_key("."))

    def wait_for(self, predicate, limit: int = DAY_TICKS) -> None:
        """Wait tick by tick until predicate() is true."""
        for _ in range(limit):
            if predicate() or self.over:
                return
            self.press(char_key("."))
        raise BotStuck("condition never became true")

    # ------------------------------------------------------- interactions
    def _open(self, kind: str, target_id: str) -> None:
        self.press(char_key("e"))
        if isinstance(self.screen, ChooserScreen):
            index = next(i for i, t in enumerate(self.screen.targets) if t.kind == kind and t.id == target_id)
            self.press(char_key(str(index + 1)))

    def talk(self, npc_id: str, *topics: str) -> None:
        """Reach an NPC, open the conversation, pick topics in order, leave."""
        self.chase(npc_id)
        if self.over:
            return
        self._open("npc", npc_id)
        if not isinstance(self.screen, DialogueScreen):
            raise BotStuck(f"no dialogue with {npc_id}")
        for topic in topics:
            ids = [opt[0] for opt in self.screen._options()]
            if topic not in ids:
                raise BotStuck(f"{npc_id} does not offer '{topic}' at {self.game.clock()} (has {ids})")
            self.press(char_key(str(ids.index(topic) + 1)))
            if not isinstance(self.screen, DialogueScreen):
                return
        self.press(KeyEvent(K.ESC))

    def use(self, object_id: str) -> None:
        """Walk to an object and use it."""
        obj = next(o for o in self.game.content.objects if o.id == object_id)
        self.walk_next_to(obj.pos)
        if not self.over:
            self._open("object", object_id)

    def end_loop(self) -> None:
        """Let the flood come, then continue to the next loop."""
        self.wait_until("14:00")
        if isinstance(self.screen, LoopEndScreen):
            self.press(KeyEvent(K.ENTER))

    def wait_for_win(self) -> None:
        """Wait until the loop ends (hopefully saved)."""
        while not self.over:
            self.wait_until("14:00")

    @property
    def won(self) -> bool:
        """True if the win screen is showing."""
        return isinstance(self.screen, WinScreen)


# -------------------------------------------------------------- routes
def learn_chain(bot: Bot, with_back_door: bool = False) -> None:
    """Loop 1: gather every fact needed (optionally Kai's secret too), then flood."""
    if with_back_door:
        bot.walk_to(bot.game.world.region("mill").spot(0))
        bot.wait_for(lambda: bot.game.place_of("kai") == "mill" and
                     chebyshev(bot.game.state.npcs["kai"].pos, bot.game.state.player.pos) <= 3)
        bot.talk("kai", "secret")
    bot.use("gauge")
    bot.wait_until("11:00")
    bot.use("gauge")
    bot.talk("vera", "gauge")
    bot.talk("ilse", "oskar")
    bot.end_loop()


def honest_route(bot: Bot) -> None:
    """Get the key from Tomas before his bus, convince Vera, give her the key."""
    learn_chain(bot)
    bot.talk("tomas", "tab")
    bot.talk("vera", "gauge", "give_key")
    bot.wait_for_win()


def sneaky_route(bot: Bot) -> None:
    """Let Tomas leave, slip in the back door unseen, take the key from the shelf."""
    learn_chain(bot, with_back_door=True)
    game = bot.game
    back = next(d for d in game.content.doors if d.id == "bar_back")
    outside = (back.pos[0], back.pos[1] - 1)
    bot.walk_to(outside)
    bot.wait_for(lambda: game.npc_gone("tomas") and not rumours.witnesses(
        game.state, game.content, back.pos, game.content.rules.witness_radius, True))
    bot.walk_to(back.pos)
    bot.use("key_shelf")
    if "key" not in game.state.player.items:
        raise BotStuck("shelf gave no key")
    bot.talk("vera", "gauge", "give_key")
    bot.wait_for_win()


def demo_route(bot: Bot) -> None:
    """The pitch demo: two instructive floods, then a clean win in loop 3."""
    bot.use("gauge")
    bot.wait_until("11:00")
    bot.use("gauge")
    bot.end_loop()
    bot.talk("vera", "gauge")
    bot.talk("ilse", "oskar")
    bot.end_loop()
    bot.talk("tomas", "tab")
    bot.talk("vera", "gauge", "give_key")
    bot.wait_for_win()


def idle_route(bot: Bot, loops: int = 3) -> None:
    """A player who does nothing: should flood every loop."""
    for _ in range(loops):
        bot.end_loop()


ROUTES = {"honest": honest_route, "sneaky": sneaky_route, "demo": demo_route, "idle": idle_route}


def play(route: str, seed: int = 1, record: Path | None = None) -> Bot:
    """Run a route and return the bot (inspect bot.won, bot.game.state)."""
    bot = Bot(seed=seed, record=record)
    try:
        ROUTES[route](bot)
    finally:
        if bot.app.recorder is not None:
            bot.app.recorder.close()
    return bot


def main(argv: list[str] | None = None) -> int:
    """CLI: run a route and print the result."""
    parser = argparse.ArgumentParser(prog="python -m rerun.solver.bot")
    parser.add_argument("--route", choices=sorted(ROUTES), default="honest")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--record", type=Path, help="save the bot's key presses as a replay file")
    args = parser.parse_args(argv)
    try:
        bot = play(args.route, args.seed, args.record)
    except BotStuck as exc:
        print(f"bot got stuck: {exc}")
        return 1
    s = bot.game.state
    outcome = "SAVED" if bot.won else (s.outcome.value if s.outcome else "running")
    print(f"route={args.route} seed={args.seed} outcome={outcome} loops={len(s.stats.outcomes)} "
          f"history={''.join(s.stats.outcomes)} time={tick_to_hhmm(s.tick)} keys={bot.presses}")
    return 0 if bot.won or args.route == "idle" else 1


if __name__ == "__main__":
    sys.exit(main())
