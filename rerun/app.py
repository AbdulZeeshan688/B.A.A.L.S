"""The application: a stack of screens, the main loop, and game-flow glue.

Main loop: read key -> current screen handles it -> render. All game
changes go through core.engine.Game; screens only call App/Game methods.
"""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from pathlib import Path

from .core.content import Content, load_content
from .core.engine import Game, Target
from .core.knowledge import Notebook
from .core.state import Event, Outcome, Stats
from .extras.replay import Recorder
from .persistence.save import RunData, SaveStore
from .ui import keys as K
from .ui.keys import KeyEvent
from .ui.renderer import Canvas
from .ui.screens.base import HEIGHT, WIDTH, Screen
from .ui.screens.dialogue import DialogueScreen
from .ui.screens.endings import LoopEndScreen, WinScreen, resize_canvas
from .ui.screens.game import GameScreen
from .ui.screens.menus import TitleScreen
from .ui.terminal import IO
from .ui.theme import Theme

LOG_LIMIT = 50
ANIMATION_STEP = 0.11
IDLE_TIMEOUT = 0.5


@dataclass
class Options:
    """Command-line options."""

    new: bool = False
    seed: int | None = None
    mono: bool = False
    ascii: bool = False
    plain: bool = False
    reduced_motion: bool = False
    record: Path | None = None
    replay: Path | None = None
    debug: bool = False
    pack: str = "marrow"
    daily: bool = False
    replay_delay: float = 0.2


class App:
    """Owns the screens, the current Game, settings and the save file."""

    def __init__(self, options: Options, io: IO, store: SaveStore, theme: Theme,
                 content: Content | None = None, force_ascii: bool = False) -> None:
        self.options = options
        self.io = io
        self.store = store
        self.theme = theme
        self.force_ascii = force_ascii
        self.content = content or load_content(options.pack)
        self.save_data, notice = store.load()
        if options.new:
            self.save_data.run = None  # keep settings and best score, drop the run
        self.settings = self.save_data.settings
        self.game: Game | None = None
        self.stack: list[Screen] = []
        self.log: list[Event] = []
        self.running = True
        self.recorder: Recorder | None = None
        self.replay_keys: list[KeyEvent] = []
        self.apply_theme()
        if notice:
            self.notify(notice, "warn")

    # ------------------------------------------------------------ settings
    @property
    def reduced_motion(self) -> bool:
        """True if animations should be skipped."""
        return self.settings.reduced_motion or self.options.reduced_motion or self.options.plain

    def apply_theme(self) -> None:
        """Recompute colours/charset from settings + flags + environment."""
        self.theme.color = (self.settings.color and not self.options.mono and not self.options.plain
                            and "NO_COLOR" not in os.environ)
        self.theme.ascii_only = self.settings.ascii_only or self.options.ascii or self.force_ascii
        self.io.invalidate()

    # --------------------------------------------------------------- stack
    def push(self, screen: Screen) -> None:
        """Show a screen on top."""
        self.stack.append(screen)

    def pop(self) -> None:
        """Close the top screen."""
        if self.stack:
            self.stack.pop()

    def reset_to(self, screen: Screen) -> None:
        """Replace the whole stack."""
        self.stack = [screen]

    # ---------------------------------------------------------- game flow
    def start(self) -> None:
        """Pick the first screen."""
        if self.options.replay is not None or self.options.record is not None or self.options.daily:
            self.new_game(self.options.seed)
            if self.options.record is not None:
                self.recorder = Recorder(self.options.record, self.game.state.seed, self.content.pack)
        else:
            self.reset_to(TitleScreen(self))

    def new_game(self, seed: int | None = None) -> None:
        """Start loop 1 with an empty notebook."""
        if seed is None:
            seed = self.options.seed if self.options.seed is not None else random.SystemRandom().randrange(10**6)
        self.game = Game(self.content, seed)
        warnings = [e for e in self.log if e.kind == "warn"]
        self.log = []
        self.collect_events()
        self.notify("Tip: stand next to someone and press E to talk. Press ? for help.", "important")
        self.log.extend(warnings)  # e.g. "save file was corrupt" stays visible
        self.reset_to(GameScreen(self))
        self.persist()

    def new_game_from_title(self) -> None:
        """Title menu 'New game' (asks first if it would wipe a run)."""
        from .ui.screens.menus import ConfirmScreen

        if self.save_data.run is not None:
            self.push(ConfirmScreen(self, "Start over? Your current notebook will be lost.", self.new_game))
        else:
            self.new_game()

    def continue_game(self) -> None:
        """Resume a saved run at 08:00 of the saved loop."""
        run = self.save_data.run
        if run is None:
            self.new_game()
            return
        notebook = Notebook.from_dict(run.notebook, set(self.content.facts))
        self.game = Game(self.content, run.seed, notebook, run.loop, Stats.from_dict(run.stats))
        self.game.state.ghost = [tuple(p) for p in run.ghost]
        self.log = []
        self.collect_events()
        self.reset_to(GameScreen(self))

    def to_title(self, save: bool = True) -> None:
        """Back to the title screen."""
        if save:
            self.persist()
        self.game = None
        self.reset_to(TitleScreen(self))

    def quit(self) -> None:
        """Stop the main loop (saving first)."""
        self.persist()
        self.running = False

    def notify(self, text: str, kind: str = "info") -> None:
        """Show a message on the game screen's message line."""
        self.log.append(Event(text, kind))
        del self.log[:-LOG_LIMIT]

    def collect_events(self) -> None:
        """Move engine events into the message log."""
        if self.game:
            for event in self.game.drain_events():
                self.notify(event.text, event.kind)

    def after_action(self) -> None:
        """Called after every time-costing action: show events, handle loop end."""
        self.collect_events()
        if self.game is None or self.game.state.outcome is None:
            return
        if self.game.state.outcome == Outcome.SAVED:
            self.finish_run()
            self.push(WinScreen(self))
        else:
            self.persist()
            self.push(LoopEndScreen(self))

    def interact(self, target: Target) -> None:
        """Talk to an NPC or use an object."""
        game = self.game
        if target.kind == "npc":
            greeting = game.talk(target.id)
            self.collect_events()
            if game.state.outcome:
                self.after_action()
            else:
                self.push(DialogueScreen(self, target.id, greeting))
        else:
            text = game.inspect(target.id)
            events = game.drain_events()
            if text:
                self.notify(text)
            for event in events:
                self.notify(event.text, event.kind)
            self.after_action()

    def skip_to(self, text: str) -> str | None:
        """Skip-time prompt callback."""
        error = self.game.skip_to(text)
        if error:
            return error
        self.after_action()
        return None

    def restart_loop(self) -> None:
        """Confirmed 'R': end this loop now."""
        self.game.restart_loop()
        self.after_action()

    def start_next_loop(self) -> None:
        """After the loop-end screen: rewind to 08:00."""
        self.game.next_loop()
        self.collect_events()
        self.persist()

    def finish_run(self) -> None:
        """A win: record the best score and clear the saved run."""
        if self.options.daily:
            return  # the daily challenge never touches the main save
        loops = len(self.game.state.stats.outcomes)
        best = self.save_data.best_loops
        self.save_data.best_loops = loops if best is None else min(best, loops)
        self.save_data.run = None
        self._write_save()

    def persist(self) -> None:
        """Save settings and (if a run is active) knowledge + stats."""
        game = self.game
        if game is not None and game.state.outcome != Outcome.SAVED and not self.options.daily:
            s = game.state
            loop = s.loop + 1 if s.outcome else s.loop
            ghost = s.player.trail if s.outcome else s.ghost
            self.save_data.run = RunData(s.seed, loop, s.notebook.to_dict(), s.stats.to_dict(),
                                         [list(p) for p in ghost])
            if s.outcome:  # the loop is over but not yet reset: count it
                self.save_data.run.stats = dict(s.stats.to_dict(),
                                                outcomes=s.stats.outcomes + [s.outcome.symbol])
        self._write_save()

    def _write_save(self) -> None:
        if self.options.replay is not None or self.options.record is not None:
            return  # demos and recordings never touch the player's save
        error = self.store.save(self.save_data)
        if error:
            self.notify(error, "warn")

    # ----------------------------------------------------------- main loop
    def handle_key(self, key: KeyEvent) -> None:
        """Route one key to the top screen."""
        if key.name == K.CTRL_C:
            raise KeyboardInterrupt
        if self.recorder is not None:
            self.recorder.record(key)
        if self.stack:
            self.stack[-1].handle(key)

    def render(self) -> Canvas:
        """Draw the current screen to a fresh 80x24 canvas."""
        canvas = Canvas(WIDTH, HEIGHT)
        if self.stack:
            self.stack[-1].render(canvas)
        return canvas

    def run(self) -> None:
        """Main loop until quit."""
        self.start()
        while self.running and self.stack:
            width, height = self.io.size()
            if width < WIDTH or height < HEIGHT:
                self.io.draw(resize_canvas(width, height, WIDTH, HEIGHT))
                key = self.io.read_key(0.3)
                if key is not None and key.name == K.CTRL_C:
                    raise KeyboardInterrupt
                if key is not None and key.is_char("q"):
                    self.quit()
                continue
            screen = self.stack[-1]
            self.io.draw(self.render())
            key = self._next_key(screen)
            if key is None:
                screen.on_timer()
            else:
                self.handle_key(key)
        if self.recorder is not None:
            self.recorder.close()

    def _next_key(self, screen: Screen) -> KeyEvent | None:
        if self.replay_keys:
            if screen.animating:
                time.sleep(ANIMATION_STEP)
                return None
            time.sleep(self.options.replay_delay)
            return self.replay_keys.pop(0)
        timeout = ANIMATION_STEP if screen.animating else IDLE_TIMEOUT
        return self.io.read_key(timeout, screen.text_mode)
