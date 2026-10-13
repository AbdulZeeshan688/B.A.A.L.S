"""Title, help, settings, confirm and text-prompt screens."""

from __future__ import annotations

import time
from typing import Callable

from .. import keys as K
from ..keys import KeyEvent
from ..renderer import Canvas, wrap
from .base import Screen, key_bar, number_key

LOGO = [
    r" ____    _____   ____    _   _   _   _ ",
    r"|  _ \  | ____| |  _ \  | | | | | \ | |",
    r"| |_) | |  _|   | |_) | | | | | |  \| |",
    r"|  _ <  | |___  |  _ <  | |_| | | |\  |",
    r"|_| \_\ |_____| |_| \_\  \___/  |_| \_|",
]

SKYLINE = [
    r"  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  ",
    r"  ==============================##===============================  ",
    r"     _____       |~~|      ___          +--+    /\        ____      ",
    r"  __|  V  |______|~~|_____| B |___.____|TH|___/MI\______| CA |____  ",
]

WAVE = "~~^~~~~^~~~^^~~~~~^~~~~~~^~~~^~~~~"


class TitleScreen(Screen):
    """Logo, animated reservoir, main menu."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self.cursor = 0
        self.started = time.monotonic()
        self.animating = not app.reduced_motion

    def _items(self) -> list[tuple[str, Callable[[], None]]]:
        app = self.app
        items = []
        if app.save_data.run is not None:
            items.append((f"Continue  (loop {app.save_data.run.loop})", app.continue_game))
        items += [("New game", app.new_game_from_title), ("How to play", lambda: app.push(HelpScreen(app))),
                  ("Settings", lambda: app.push(SettingsScreen(app))), ("Quit", app.quit)]
        return items

    def render(self, c: Canvas) -> None:
        for i, line in enumerate(LOGO):
            c.center(2 + i, line, "logo")
        c.center(8, self.app.content.tagline, "bold")
        phase = int((time.monotonic() - self.started) * 4) if self.animating else 0
        for i, line in enumerate(SKYLINE):
            style = "water" if i == 0 else ("dam" if i == 1 else "wall")
            if i == 0:
                line = "  " + (WAVE * 3)[phase % len(WAVE):][: len(line) - 4] + "  "
            c.center(10 + i, line, style)
        items = self._items()
        for i, (label, _) in enumerate(items):
            selected = i == self.cursor
            c.center(15 + i, f"{'>' if selected else ' '} {i + 1}. {label:<22}", "select" if selected else "")
        best = self.app.save_data.best_loops
        if best:
            c.center(21, f"Best: Marrow saved in {best} loop{'s' if best != 1 else ''}", "ok")
        key_bar(c, 23, "[W/S or arrows] move  [Enter] choose  [1-5] quick pick  [Q] quit")

    def on_timer(self) -> None:
        pass  # Redraw happens every frame; the wave moves with the clock.

    def handle(self, key: KeyEvent) -> None:
        items = self._items()
        num = number_key(key)
        if key.name == K.UP or key.is_char("w"):
            self.cursor = (self.cursor - 1) % len(items)
        elif key.name == K.DOWN or key.is_char("s"):
            self.cursor = (self.cursor + 1) % len(items)
        elif key.is_char("q") or key.name == K.ESC:
            self.app.quit()
        elif num is not None and num <= len(items):
            self.cursor = num - 1
            items[num - 1][1]()
        elif key.name == K.ENTER or key.is_char("e"):
            items[self.cursor][1]()


HELP = [
    ("GOAL", "bold"),
    ("At 14:00 the dam breaks and Marrow floods. Then it's 08:00 again.", ""),
    ("You keep only your NOTEBOOK. Learn who knows what, and stop the flood.", ""),
    ("Options marked [from notes] exist because of something you learned.", ""),
    ("", ""),
    ("CONTROLS   every action costs 2 minutes; choosing what to say is free", "bold"),
    ("  WASD / arrows  move              E / Enter  talk to / use what's next to you", ""),
    ("  . / space      wait              T          skip to a time (stops on events)", ""),
    ("  N              notebook          G          ghost trail of your last loop", ""),
    ("  !              shout a warning   R          restart loop     Q  save & quit", ""),
    ("", ""),
    ("MAP", "bold"),
    ("  @ you    V T I M K O people    ~ water    = dam    + - | walls    ^ forest", ""),
    ("  D door   x locked door    g water gauge    & shelf    : your last loop", ""),
    ("", ""),
    ("TIPS", "bold"),
    ("  People follow the same schedule every loop. Be where they are.", ""),
    ("  Being seen doing shady things starts rumours. Rumours travel.", ""),
]


class HelpScreen(Screen):
    """How to play."""

    def render(self, c: Canvas) -> None:
        c.box(0, 0, 80, 23, "HOW TO PLAY", title_style="title")
        for i, (text, style) in enumerate(HELP):
            c.put(2, 2 + i, text[:76], style)
        key_bar(c, 23, "[Esc/Enter] back")

    def handle(self, key: KeyEvent) -> None:
        if key.name in (K.ESC, K.ENTER) or key.is_char("q", "?", "h"):
            self.app.pop()


class SettingsScreen(Screen):
    """Toggle colour, ASCII-only, reduced motion, ghost trail."""

    FIELDS = [("color", "Colours"), ("ascii_only", "ASCII-only characters"),
              ("reduced_motion", "Reduced motion"), ("ghost", "Ghost trail")]

    def render(self, c: Canvas) -> None:
        c.box(15, 5, 50, 12, "SETTINGS", title_style="title")
        for i, (field, label) in enumerate(self.FIELDS):
            value = getattr(self.app.settings, field)
            c.put(18, 7 + i * 2, f"{i + 1}) {label:<26} [{'ON ' if value else 'OFF'}]", "ok" if value else "")
        if self.app.options.mono or self.app.options.ascii:
            c.put(18, 15, "(command-line flags override these)", "dim")
        key_bar(c, 23, "[1-4] toggle  [Esc] back")

    def handle(self, key: KeyEvent) -> None:
        num = number_key(key)
        if key.name in (K.ESC, K.ENTER) or key.is_char("q"):
            self.app.pop()
        elif num is not None and num <= len(self.FIELDS):
            field = self.FIELDS[num - 1][0]
            setattr(self.app.settings, field, not getattr(self.app.settings, field))
            self.app.apply_theme()
            self.app.persist()


class ConfirmScreen(Screen):
    """Yes/no question."""

    overlay = True

    def __init__(self, app, question: str, on_yes: Callable[[], None]) -> None:
        super().__init__(app)
        self.question = question
        self.on_yes = on_yes

    def render(self, c: Canvas) -> None:
        lines = wrap(self.question, 44)
        c.box(15, 8, 50, len(lines) + 4, "Are you sure?", style="bold", title_style="warn")
        for i, line in enumerate(lines):
            c.put(18, 9 + i, line)
        c.put(18, 10 + len(lines), "[Y] yes    [N] no", "bold")

    def handle(self, key: KeyEvent) -> None:
        if key.is_char("y"):
            self.app.pop()
            self.on_yes()
        elif key.is_char("n", "q") or key.name == K.ESC:
            self.app.pop()


class PromptScreen(Screen):
    """Single-line text input. `on_submit` returns an error message or None."""

    overlay = True
    text_mode = True

    def __init__(self, app, question: str, on_submit: Callable[[str], str | None],
                 placeholder: str = "", error: str = "") -> None:
        super().__init__(app)
        self.question = question
        self.on_submit = on_submit
        self.placeholder = placeholder
        self.buffer = ""
        self.error = error

    def render(self, c: Canvas) -> None:
        lines = wrap(self.question, 50)
        h = len(lines) + 6
        c.box(12, 7, 56, h, "Skip time", style="bold", title_style="title")
        for i, line in enumerate(lines):
            c.put(15, 8 + i, line)
        y = 9 + len(lines)
        shown = self.buffer or self.placeholder
        c.put(15, y, "> " + shown + ("_" if self.buffer else ""), "bold" if self.buffer else "dim")
        if self.error:
            c.put(15, y + 1, self.error[:50], "warn")
        c.fill(0, 23, 80, 1)
        key_bar(c, 23, "type a time like 11:00  [Enter] go  [Esc] cancel")

    def handle(self, key: KeyEvent) -> None:
        if key.name == K.ESC:
            self.app.pop()
        elif key.name == K.BACKSPACE:
            self.buffer = self.buffer[:-1]
        elif key.name == K.ENTER:
            self.app.pop()
            error = self.on_submit(self.buffer)
            if error:
                self.app.push(PromptScreen(self.app, self.question, self.on_submit, self.placeholder, error))
        elif key.name == K.CHAR and len(self.buffer) < 8:
            self.buffer += key.char
            self.error = ""
