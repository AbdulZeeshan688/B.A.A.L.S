"""Raw keyboard input on macOS / Linux using termios."""

from __future__ import annotations

import os
import select
import sys
import termios
import tty

from .keys import KeyEvent, parse_unix


class UnixInput:
    """Puts stdin into cbreak mode and reads keys with a timeout."""

    def __init__(self) -> None:
        self.fd = sys.stdin.fileno()
        self._saved = None
        self._pending: list[KeyEvent] = []

    def start(self) -> None:
        """Enter cbreak mode (no echo, no line buffering; Ctrl+C still raises)."""
        self._saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)

    def stop(self) -> None:
        """Restore the terminal settings saved by start(). Safe to call twice."""
        if self._saved is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._saved)
            self._saved = None

    def read_key(self, timeout: float | None) -> KeyEvent | None:
        """Next key, or None if nothing arrived within `timeout` seconds."""
        if self._pending:
            return self._pending.pop(0)
        ready, _, _ = select.select([self.fd], [], [], timeout)
        if not ready:
            return None
        data = os.read(self.fd, 64)
        if not data:
            raise EOFError("stdin closed")
        # A lone ESC may be the start of a sequence split across reads.
        if data == b"\x1b":
            more, _, _ = select.select([self.fd], [], [], 0.03)
            if more:
                data += os.read(self.fd, 64)
        self._pending.extend(parse_unix(data.decode("utf-8", errors="ignore")))
        return self._pending.pop(0) if self._pending else None
