"""End-of-loop screens: the flood (or arrest / restart), and the win screen with share card."""

from __future__ import annotations

from ...core.clock import tick_to_hhmm
from ...core.state import Outcome
from ...extras.share import share_line, time_used_text
from .. import keys as K
from ..keys import KeyEvent
from ..renderer import Canvas
from .base import Screen, key_bar
from .game import draw_game, draw_map

FLOOD_ROWS = 18
FRAMES_PER_ROW = 1  # one map row per timer tick (~2 s total)

HEADLINES = {
    Outcome.FLOODED: "14:00 — THE DAM BROKE",
    Outcome.ARRESTED: "{time} — ARRESTED",
    Outcome.RESTARTED: "{time} — YOU LET THE DAY GO",
}

VALVE = [
    r"        _______        ",
    r"     .-'   |   '-.     ",
    r"    /      |      \    ",
    r"   |-------O-------|   ",
    r"    \      |      /    ",
    r"     '-.___|___.-'     ",
    r"           ||          ",
    r"  =========##========  ",
]


class LoopEndScreen(Screen):
    """Flood animation (if flooded), then a summary of what this loop taught you."""

    def __init__(self, app) -> None:
        super().__init__(app)
        game = app.game
        self.outcome = game.state.outcome
        self.loop = game.state.loop
        self.time = tick_to_hhmm(game.state.tick)
        self.new_facts = game.state.notebook.learned_in(self.loop)
        animate = self.outcome == Outcome.FLOODED and not app.reduced_motion
        self.rows = 0 if animate else FLOOD_ROWS
        self.animating = animate

    def render(self, c: Canvas) -> None:
        if self.outcome == Outcome.FLOODED:
            draw_game(c, self.app)
            draw_map(c, self.app.game, False, flood_rows=self.rows)
        else:
            draw_game(c, self.app)
        if self.rows < FLOOD_ROWS:
            return
        facts = self.app.game.content.facts
        shown = self.new_facts[:6]
        h = 9 + len(shown)
        bx, bw = 5, 52  # stays left of the notebook panel
        c.box(bx, 4, bw, h, "LOOP OVER", style="bold", title_style="warn")
        c.center(6, HEADLINES[self.outcome].format(time=self.time), "warn", x=bx, w=bw)
        c.center(7, f"Loop {self.loop} ended.", "", x=bx, w=bw)
        c.center(8, f"New in your notebook: {len(self.new_facts)}", "fact" if self.new_facts else "dim", x=bx, w=bw)
        for i, fact_id in enumerate(shown):
            c.put(bx + 6, 10 + i, f"+ {facts[fact_id].short}", "note_new")
        c.center(4 + h - 2, f"[Enter] start loop {self.loop + 1}    [N] notebook", "bold", x=bx, w=bw)
        c.fill(0, 23, 80, 1)
        key_bar(c, 23, "[Enter] next loop  [N] notebook")

    def on_timer(self) -> None:
        if self.rows < FLOOD_ROWS:
            self.rows += 1
        self.animating = self.rows < FLOOD_ROWS

    def handle(self, key: KeyEvent) -> None:
        from .notebook import NotebookScreen

        if self.rows < FLOOD_ROWS:
            if key.name in (K.ENTER, K.ESC) or key.is_char(" ", "e"):
                self.rows, self.animating = FLOOD_ROWS, False
            return
        if key.name == K.ENTER or key.is_char("e", " "):
            self.app.pop()
            self.app.start_next_loop()
        elif key.is_char("n"):
            self.app.push(NotebookScreen(self.app))


class WinScreen(Screen):
    """Marrow is saved. Stats and a spoiler-free share line."""

    def __init__(self, app) -> None:
        super().__init__(app)
        s = app.game.state
        self.time = tick_to_hhmm(s.tick)
        self.share = share_line(s.seed, s.stats.outcomes)
        self.stats = s.stats

    def render(self, c: Canvas) -> None:
        c.box(0, 0, 80, 23, "RERUN", style="ok", title_style="ok")
        for i, line in enumerate(VALVE):
            c.center(2 + i, line, "water_hi" if i == 7 else "ok")
        c.center(11, "THE VALVE OPENS. MARROW IS SAFE.", "ok")
        c.center(12, f"Vera turns the wheel at {self.time}. The water roars down the spillway.", "")
        loops = len(self.stats.outcomes)
        c.center(14, f"Loops: {loops}    In-game time used: {time_used_text(self.stats.ticks_used)}    "
                     f"Rumours started: {self.stats.rumours_started}", "bold")
        c.center(16, "Share (no spoilers):", "dim")
        c.center(17, self.share, "note_new")
        c.center(19, "~ flooded   ^ arrested   * saved", "dim")
        key_bar(c, 23, "[Enter] title screen  [Q] quit")

    def handle(self, key: KeyEvent) -> None:
        if key.name == K.ENTER or key.is_char("e", " "):
            self.app.to_title(save=False)
        elif key.is_char("q") or key.name == K.ESC:
            self.app.quit()


def resize_canvas(width: int, height: int, need_w: int, need_h: int) -> Canvas:
    """Shown instead of the game when the terminal is too small."""
    w, h = max(1, width), max(1, height)
    c = Canvas(w, h)
    lines = ["RERUN needs a bigger window.", f"Please make it at least {need_w}x{need_h}",
             f"(now: {width}x{height}).", "", "The game resumes automatically.", "[Q] quit"]
    top = max(0, (h - len(lines)) // 2)
    for i, line in enumerate(lines):
        c.center(top + i, line[:w], "warn" if i == 0 else "")
    return c
