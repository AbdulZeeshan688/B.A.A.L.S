"""Screen base class and small drawing helpers shared by all screens."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..keys import KeyEvent
from ..renderer import Canvas

if TYPE_CHECKING:
    from ...app import App

WIDTH, HEIGHT = 80, 24
_KEY_RE = re.compile(r"(\[[^\]]+\])")


class Screen:
    """One screen on the app's stack. Subclasses override render/handle."""

    animating = False  # True -> app wakes up often to call on_timer()
    text_mode = False  # True -> plain mode sends Enter after typed text
    overlay = False  # True -> draw the screen below first

    def __init__(self, app: "App") -> None:
        self.app = app

    def render(self, c: Canvas) -> None:
        """Draw onto the 80x24 canvas."""

    def handle(self, key: KeyEvent) -> None:
        """React to a key press."""

    def on_timer(self) -> None:
        """Called when no key arrived within the timeout."""


def key_bar(c: Canvas, y: int, text: str, x: int = 1) -> None:
    """Draw a help line where [X] segments stand out."""
    for part in _KEY_RE.split(text):
        if part:
            x = c.put(x, y, part, "bold" if part.startswith("[") else "dim")


def number_key(key: KeyEvent) -> int | None:
    """1-9 -> 1-9, else None."""
    if key.name == "CHAR" and key.char.isdigit() and key.char != "0":
        return int(key.char)
    return None
