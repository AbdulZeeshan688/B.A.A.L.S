"""Colours and character sets. Colour is decoration only, never the only signal."""

from __future__ import annotations

from dataclasses import dataclass

RESET = "\x1b[0m"

# style name -> (SGR codes in colour mode, SGR codes in mono mode)
_STYLES: dict[str, tuple[str, str]] = {
    "": ("", ""),
    "water": ("34", ""),
    "water_hi": ("96;1", "1"),
    "dam": ("97;1", "1"),
    "wall": ("37", ""),
    "label": ("90", "2"),
    "road": ("90", "2"),
    "forest": ("32", ""),
    "door": ("33", ""),
    "locked": ("31", ""),
    "object": ("96;1", "1"),
    "player": ("97;44;1", "1;7"),
    "ghost": ("36;2", "2"),
    "title": ("96;1", "1"),
    "logo": ("96;1", "1"),
    "bold": ("1", "1"),
    "dim": ("90", "2"),
    "note": ("33", ""),
    "note_new": ("93;1", "1"),
    "fact": ("93;1", "1"),
    "warn": ("91;1", "1"),
    "rumour": ("95", ""),
    "ok": ("92;1", "1"),
    "key": ("30;47", "7"),
    "select": ("30;46", "7"),
    "bar_fill": ("36", ""),
    "bar_late": ("91;1", "1"),
    "border": ("37", ""),
}

_NPC_COLOURS = {"red": "91", "green": "92", "yellow": "93", "blue": "94", "magenta": "95", "cyan": "96", "white": "97"}

ASCII_MAP = str.maketrans({
    "─": "-", "│": "|", "┌": "+", "┐": "+", "└": "+", "┘": "+", "├": "+", "┤": "+",
    "═": "=", "║": "|", "╔": "+", "╗": "+", "╚": "+", "╝": "+",
    "█": "#", "░": ".", "▓": "#", "·": ".", "—": "-", "…": "...", "→": ">", "•": "*",
    "≈": "~", "▲": "^", "▼": "v", "⭐": "*", "●": "o", "○": ".",
})

UNICODE_PROBE = "─│┌█░·—…→≈"


@dataclass
class Theme:
    """How styles become ANSI codes, and which characters are allowed."""

    color: bool = True
    ascii_only: bool = False
    ansi: bool = True

    def sgr(self, style: str) -> str:
        """ANSI start sequence for a style name ('' for none)."""
        if not self.ansi or not style:
            return ""
        if style.startswith("npc:"):
            colour = _NPC_COLOURS.get(style[4:], "97")
            return f"\x1b[{colour};1m" if self.color else "\x1b[1m"
        colour, mono = _STYLES.get(style, ("", ""))
        codes = colour if self.color else mono
        return f"\x1b[{codes}m" if codes else ""

    def text(self, s: str) -> str:
        """Apply ASCII replacements when needed."""
        return s.translate(ASCII_MAP) if self.ascii_only else s


def can_encode_unicode(encoding: str | None) -> bool:
    """True if the output encoding can show our box-drawing characters."""
    try:
        UNICODE_PROBE.encode(encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False
