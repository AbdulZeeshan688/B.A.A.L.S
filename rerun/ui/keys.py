"""Normalise raw key input (Unix escape sequences, Windows scan codes) to KeyEvents."""

from __future__ import annotations

from dataclasses import dataclass

UP, DOWN, LEFT, RIGHT = "UP", "DOWN", "LEFT", "RIGHT"
ENTER, ESC, BACKSPACE, TAB, CTRL_C, CHAR = "ENTER", "ESC", "BACKSPACE", "TAB", "CTRL_C", "CHAR"


@dataclass(frozen=True)
class KeyEvent:
    """One key press. `char` is set only when name == CHAR."""

    name: str
    char: str = ""

    def is_char(self, *chars: str) -> bool:
        """True if this is a printable key matching any of `chars` (case-insensitive)."""
        return self.name == CHAR and self.char.lower() in chars

    def to_dict(self) -> dict:
        """Serialise for replay files."""
        return {"k": self.name, "c": self.char} if self.char else {"k": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> "KeyEvent":
        """Inverse of to_dict. Raises ValueError on junk."""
        name = data.get("k")
        if name not in (UP, DOWN, LEFT, RIGHT, ENTER, ESC, BACKSPACE, TAB, CTRL_C, CHAR):
            raise ValueError(f"unknown key {name!r}")
        char = str(data.get("c", ""))
        if name == CHAR and len(char) != 1:
            raise ValueError("CHAR key needs exactly one character")
        return cls(name, char)


def char_key(ch: str) -> KeyEvent:
    """KeyEvent for a printable character."""
    return KeyEvent(CHAR, ch)


_CSI_FINAL = {"A": UP, "B": DOWN, "C": RIGHT, "D": LEFT}
_CONTROL = {"\r": ENTER, "\n": ENTER, "\t": TAB, "\x7f": BACKSPACE, "\x08": BACKSPACE, "\x03": CTRL_C}


def parse_unix(data: str) -> list[KeyEvent]:
    """Parse a chunk of terminal input into keys.

    Handles CSI (ESC [ A) and SS3 (ESC O A) arrows, a lone ESC, control
    keys and printable characters. Unknown sequences are dropped.
    """
    keys: list[KeyEvent] = []
    i = 0
    while i < len(data):
        ch = data[i]
        if ch == "\x1b":
            if i + 1 >= len(data):
                keys.append(KeyEvent(ESC))
                i += 1
                continue
            nxt = data[i + 1]
            if nxt in "[O":
                j = i + 2
                while j < len(data) and not ("@" <= data[j] <= "~"):
                    j += 1
                if j < len(data) and data[j] in _CSI_FINAL:
                    keys.append(KeyEvent(_CSI_FINAL[data[j]]))
                i = j + 1
                continue
            keys.append(KeyEvent(ESC))
            i += 1
            continue
        if ch in _CONTROL:
            keys.append(KeyEvent(_CONTROL[ch]))
        elif ch.isprintable():
            keys.append(char_key(ch))
        i += 1
    return keys


_WIN_SCAN = {"H": UP, "P": DOWN, "K": LEFT, "M": RIGHT}
WIN_PREFIXES = ("\x00", "\xe0")


def parse_windows(first: str, second: str = "") -> KeyEvent | None:
    """Map msvcrt.getwch() output to a KeyEvent.

    Arrow keys arrive as a prefix ('\\x00' or '\\xe0') followed by a scan code.
    """
    if first in WIN_PREFIXES:
        name = _WIN_SCAN.get(second)
        return KeyEvent(name) if name else None
    if first == "\x1b":
        return KeyEvent(ESC)
    if first in _CONTROL:
        return KeyEvent(_CONTROL[first])
    if first.isprintable():
        return char_key(first)
    return None


def parse_line(line: str) -> list[KeyEvent]:
    """Plain mode: turn a typed line into keys ('wwd' -> W, W, D; 'esc' -> ESC)."""
    words = {"up": UP, "down": DOWN, "left": LEFT, "right": RIGHT, "esc": ESC, "enter": ENTER}
    stripped = line.strip()
    if not stripped:
        return [KeyEvent(ENTER)]
    if stripped.lower() in words:
        return [KeyEvent(words[stripped.lower()])]
    return [char_key(c) for c in stripped if c.isprintable()]
