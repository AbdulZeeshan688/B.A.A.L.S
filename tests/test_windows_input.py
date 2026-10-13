"""Exercise the Windows key reader with a fake msvcrt (runs on any OS)."""

import sys
import types

from rerun.ui.keys import CHAR, ENTER, UP, KeyEvent


def fake_msvcrt(chars):
    queue = list(chars)
    mod = types.ModuleType("msvcrt")
    mod.kbhit = lambda: bool(queue)
    mod.getwch = lambda: queue.pop(0)
    return mod


def test_windows_reader_maps_prefixed_arrows(monkeypatch):
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt(["\xe0", "H", "e", "\r"]))
    from rerun.ui.input_windows import WindowsInput

    reader = WindowsInput()
    assert reader.read_key(0.1) == KeyEvent(UP)
    assert reader.read_key(0.1) == KeyEvent(CHAR, "e")
    assert reader.read_key(0.1) == KeyEvent(ENTER)
    assert reader.read_key(0.05) is None  # timeout, no key


def test_vt_mode_fails_gracefully_off_windows():
    from rerun.ui.input_windows import enable_vt_mode

    if sys.platform != "win32":
        assert enable_vt_mode() is False
