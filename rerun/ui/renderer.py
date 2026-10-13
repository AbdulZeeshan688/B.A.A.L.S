"""Canvas (a grid of styled characters) and a renderer that redraws only changed lines."""

from __future__ import annotations

import textwrap
from typing import Callable

from .theme import RESET, Theme

BOX = {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│"}


class Canvas:
    """A fixed-size grid of characters, each with a style name."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.chars = [[" "] * width for _ in range(height)]
        self.styles = [[""] * width for _ in range(height)]

    def put(self, x: int, y: int, text: str, style: str = "") -> int:
        """Write text at (x, y), clipped to the canvas. Returns x after the text."""
        if not 0 <= y < self.height:
            return x + len(text)
        for i, ch in enumerate(text):
            cx = x + i
            if 0 <= cx < self.width:
                self.chars[y][cx] = ch
                self.styles[y][cx] = style
        return x + len(text)

    def get(self, x: int, y: int) -> str:
        """Character at (x, y)."""
        return self.chars[y][x]

    def fill(self, x: int, y: int, w: int, h: int, ch: str = " ", style: str = "") -> None:
        """Fill a rectangle."""
        for row in range(y, y + h):
            self.put(x, row, ch * w, style)

    def box(self, x: int, y: int, w: int, h: int, title: str = "", style: str = "border",
            title_style: str = "bold", footer: str = "", clear: bool = True) -> None:
        """Draw a bordered box, optionally with a title and footer in the border."""
        if clear:
            self.fill(x + 1, y + 1, w - 2, h - 2)
        self.put(x, y, BOX["tl"] + BOX["h"] * (w - 2) + BOX["tr"], style)
        self.put(x, y + h - 1, BOX["bl"] + BOX["h"] * (w - 2) + BOX["br"], style)
        for row in range(y + 1, y + h - 1):
            self.put(x, row, BOX["v"], style)
            self.put(x + w - 1, row, BOX["v"], style)
        if title:
            self.put(x + 2, y, f" {title[: w - 6]} ", title_style)
        if footer:
            self.put(x + 2, y + h - 1, f" {footer[: w - 6]} ", "dim")

    def center(self, y: int, text: str, style: str = "", x: int = 0, w: int | None = None) -> None:
        """Write text centred within [x, x+w)."""
        width = self.width if w is None else w
        self.put(x + max(0, (width - len(text)) // 2), y, text, style)

    def plain_lines(self) -> list[str]:
        """Rows as plain strings without styling."""
        return ["".join(row) for row in self.chars]


def wrap(text: str, width: int) -> list[str]:
    """Word-wrap text into lines no wider than width."""
    lines: list[str] = []
    for para in text.split("\n"):
        lines.extend(textwrap.wrap(para, width) or [""])
    return lines


class Renderer:
    """Turns canvases into ANSI output, rewriting only lines that changed."""

    def __init__(self, theme: Theme, write: Callable[[str], None]) -> None:
        self.theme = theme
        self.write = write
        self._prev: list[str] = []
        self._origin: tuple[int, int, int, int] | None = None

    def invalidate(self) -> None:
        """Force a full redraw next frame (after resize or theme change)."""
        self._prev = []
        self._origin = None

    def line(self, canvas: Canvas, y: int) -> str:
        """One canvas row as an ANSI string."""
        out: list[str] = []
        current = None
        for ch, style in zip(canvas.chars[y], canvas.styles[y]):
            if style != current:
                out.append(RESET + self.theme.sgr(style) if self.theme.ansi else "")
                current = style
            out.append(self.theme.text(ch))
        if self.theme.ansi:
            out.append(RESET)
        return "".join(out)

    def draw(self, canvas: Canvas, term_w: int, term_h: int) -> None:
        """Draw canvas centred in a terminal of the given size."""
        x0 = max(0, (term_w - canvas.width) // 2)
        y0 = max(0, (term_h - canvas.height) // 2)
        origin = (x0, y0, term_w, term_h)
        parts: list[str] = []
        if origin != self._origin:
            parts.append("\x1b[0m\x1b[2J")
            self._prev = []
            self._origin = origin
        lines = [self.line(canvas, y) for y in range(canvas.height)]
        for y, text in enumerate(lines):
            if y >= len(self._prev) or self._prev[y] != text:
                parts.append(f"\x1b[{y0 + y + 1};{x0 + 1}H{text}")
        self._prev = lines
        if parts:
            self.write("".join(parts))
