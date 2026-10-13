"""Raw keyboard input on Windows using msvcrt, plus ANSI (VT) output support."""

from __future__ import annotations

import time

from .keys import WIN_PREFIXES, KeyEvent, parse_windows

ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
STD_OUTPUT_HANDLE = -11


def enable_vt_mode() -> bool:
    """Turn on ANSI escape handling in the Windows console. Returns success."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING))
    except (AttributeError, OSError, ImportError):
        return False


class WindowsInput:
    """Polls msvcrt for keys; arrow keys come as prefix + scan code."""

    def __init__(self) -> None:
        import msvcrt

        self._msvcrt = msvcrt

    def start(self) -> None:
        """Enable VT output. msvcrt input is already unbuffered."""
        if not enable_vt_mode():
            import os

            os.system("")  # Fallback trick that enables VT mode on most consoles.

    def stop(self) -> None:
        """Nothing to restore for msvcrt."""

    def read_key(self, timeout: float | None) -> KeyEvent | None:
        """Next key, or None after `timeout` seconds."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self._msvcrt.kbhit():
            if deadline is not None and time.monotonic() >= deadline:
                return None
            time.sleep(0.01)
        first = self._msvcrt.getwch()
        second = self._msvcrt.getwch() if first in WIN_PREFIXES else ""
        return parse_windows(first, second)
