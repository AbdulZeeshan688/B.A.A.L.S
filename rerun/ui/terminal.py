"""Terminal session: alternate screen, hidden cursor, raw input, guaranteed cleanup.

Also defines the three IO backends the app can run on:
  TerminalIO  - the real game (raw keys, ANSI, redraws changed lines)
  PlainIO     - fallback: type keys + Enter, frames printed as plain text
  HeadlessIO  - no terminal at all (tests, solver bot)
"""

from __future__ import annotations

import atexit
import os
import shutil
import signal
import sys
from typing import Protocol

from .keys import KeyEvent, parse_line
from .renderer import Canvas, Renderer
from .theme import Theme

ENTER_ALT = "\x1b[?1049h"
LEAVE_ALT = "\x1b[?1049l"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"


class IO(Protocol):
    """What the app needs from a display + keyboard."""

    def size(self) -> tuple[int, int]: ...
    def draw(self, canvas: Canvas) -> None: ...
    def read_key(self, timeout: float | None, text_mode: bool = False) -> KeyEvent | None: ...
    def invalidate(self) -> None: ...


def _make_input():
    if os.name == "nt":
        from .input_windows import WindowsInput
        return WindowsInput()
    from .input_unix import UnixInput
    return UnixInput()


class TerminalIO:
    """The real terminal. Use as a context manager so cleanup always runs."""

    def __init__(self, theme: Theme) -> None:
        self.renderer = Renderer(theme, self._write)
        self._input = _make_input()
        self._active = False
        self._old_sigterm = None

    def __enter__(self) -> "TerminalIO":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.restore()

    def start(self) -> None:
        """Switch to the alternate screen and raw-ish input."""
        self._input.start()
        self._active = True
        atexit.register(self.restore)
        if hasattr(signal, "SIGTERM"):
            self._old_sigterm = signal.signal(signal.SIGTERM, _raise_exit)
        self._write(ENTER_ALT + HIDE_CURSOR + "\x1b[2J")

    def restore(self) -> None:
        """Give the terminal back exactly as we found it. Safe to call many times."""
        if not self._active:
            return
        self._active = False
        try:
            self._input.stop()
        finally:
            self._write("\x1b[0m" + SHOW_CURSOR + LEAVE_ALT)
            if self._old_sigterm is not None:
                signal.signal(signal.SIGTERM, self._old_sigterm)

    def size(self) -> tuple[int, int]:
        """Current terminal size (columns, rows)."""
        size = shutil.get_terminal_size((80, 24))
        return size.columns, size.lines

    def draw(self, canvas: Canvas) -> None:
        """Draw a frame centred in the terminal."""
        w, h = self.size()
        self.renderer.draw(canvas, w, h)

    def invalidate(self) -> None:
        """Force a full redraw."""
        self.renderer.invalidate()

    def read_key(self, timeout: float | None, text_mode: bool = False) -> KeyEvent | None:
        """Next key press, or None on timeout."""
        return self._input.read_key(timeout)

    @staticmethod
    def _write(text: str) -> None:
        try:
            sys.stdout.write(text)
            sys.stdout.flush()
        except (OSError, ValueError):
            pass  # stdout closed (e.g. pipe gone); nothing useful to do.


def _raise_exit(signum: int, frame: object) -> None:
    raise SystemExit(128 + signum)


class PlainIO:
    """Line-based fallback: works in any console, even without raw input or ANSI."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._queue: list[KeyEvent] = []
        self._last: list[str] = []

    def size(self) -> tuple[int, int]:
        """Plain mode always uses the minimum layout."""
        return 80, 24

    def draw(self, canvas: Canvas) -> None:
        """Print the frame if it changed since the last one."""
        lines = [self.theme.text(line).rstrip() for line in canvas.plain_lines()]
        if lines != self._last:
            print("\n" + "\n".join(lines), flush=True)
            self._last = lines

    def invalidate(self) -> None:
        """Reprint the next frame even if unchanged."""
        self._last = []

    def read_key(self, timeout: float | None, text_mode: bool = False) -> KeyEvent | None:
        """Read a typed line and hand out its keys one by one."""
        if not self._queue:
            line = input("text + Enter > " if text_mode else "keys + Enter > ")
            self._queue = parse_line(line)
            if text_mode and line.strip():
                self._queue.append(KeyEvent("ENTER"))
        return self._queue.pop(0) if self._queue else None


class HeadlessIO:
    """No terminal: keys come from a list, frames are kept for inspection."""

    def __init__(self, width: int = 80, height: int = 24) -> None:
        self.width, self.height = width, height
        self.keys: list[KeyEvent] = []
        self.last_frame: Canvas | None = None

    def size(self) -> tuple[int, int]:
        """Pretend terminal size."""
        return self.width, self.height

    def draw(self, canvas: Canvas) -> None:
        """Remember the frame."""
        self.last_frame = canvas

    def invalidate(self) -> None:
        """Nothing to do."""

    def read_key(self, timeout: float | None, text_mode: bool = False) -> KeyEvent | None:
        """Next scripted key, or None."""
        return self.keys.pop(0) if self.keys else None
