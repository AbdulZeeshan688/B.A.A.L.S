"""Four-page story intro shown when a new game starts from the title screen."""

from __future__ import annotations

from .. import keys as K
from ..keys import KeyEvent
from ..renderer import Canvas, wrap
from .base import Screen, key_bar

PAGES: list[tuple[str, list[tuple[str, str]], str]] = [
    ("THIS IS MARROW", [
        ("~~~~~~~~~~~~~~~~~~~~~ RESERVOIR ~~~~~~~~~~~~~~~~~~~~~", "water"),
        ("=========================##==========================", "dam"),
        ("   +----+    +------+     +-----+    +---------+     ", "wall"),
        ("___| INN|____| CAFE |_____| BAR |____|TOWN HALL|_____", "wall"),
        ("                   @  <- you                         ", "player"),
    ], "A little town under a big old dam. You just stepped off the 08:00 bus."),
    ("14:00 - THE DAM BREAKS", [
        ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~", "water"),
        ("============ ##     C R A C K !     ## ==============", "warn"),
        ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~", "water_hi"),
        ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~", "water"),
        ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~", "water_hi"),
    ], "At 2 o'clock the dam breaks and the whole town floods."),
    ("...AND THE DAY STARTS AGAIN", [
        ("   08:00 ------> 14:00 ------> 08:00 ------> 14:00   ", "bold"),
        ("     ^             |  SPLASH!   ^             |      ", "water_hi"),
        ("     +-------------+            +-------------+      ", "dim"),
        ("", ""),
        ("            Every day is the SAME day.               ", "bold"),
    ], "People do the same things at the same times, every day. You forget nothing: "
       "your NOTEBOOK keeps every secret you learn."),
    ("YOUR MISSION", [
        ("  Find out who can stop the flood,", "bold"),
        ("  and help them before 14:00.", "bold"),
        ("", ""),
        ("   ▼     a blinking arrow shows where to go", "warn"),
        ("  GOAL   the yellow line says what to do", "fact"),
    ], "Stand next to a letter (a person) and press E to talk. That's it. Good luck!"),
]


class IntroScreen(Screen):
    """Story in four pages. Enter = next, Esc = skip."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self.page = 0

    def render(self, c: Canvas) -> None:
        title, art, text = PAGES[self.page]
        c.box(0, 0, 80, 23, f"RERUN  ·  {self.page + 1}/{len(PAGES)}", title_style="title")
        c.center(3, title, "warn" if self.page == 1 else "title")
        for i, (line, style) in enumerate(art):
            c.center(6 + i, line, style)
        for i, line in enumerate(wrap(text, 60)):
            c.center(13 + i, line, "")
        dots = "  ".join("●" if i == self.page else "○" for i in range(len(PAGES)))
        c.center(19, dots, "dim")
        last = self.page == len(PAGES) - 1
        c.center(21, "[Enter] Let's go!" if last else "[Enter] next", "ok" if last else "bold")
        key_bar(c, 23, "[Enter] next  [Left] back  [Esc] skip intro")

    def handle(self, key: KeyEvent) -> None:
        if key.name == K.ESC or key.is_char("q"):
            self.app.pop()
        elif key.name == K.LEFT or key.is_char("a"):
            self.page = max(0, self.page - 1)
        elif key.name in (K.ENTER, K.RIGHT) or key.is_char(" ", "d", "e"):
            if self.page == len(PAGES) - 1:
                self.app.pop()
            else:
                self.page += 1
