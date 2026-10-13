import pytest

from rerun.ui.keys import (
    BACKSPACE,
    CHAR,
    CTRL_C,
    DOWN,
    ENTER,
    ESC,
    LEFT,
    RIGHT,
    UP,
    KeyEvent,
    parse_line,
    parse_unix,
    parse_windows,
)


@pytest.mark.parametrize("seq,name", [("\x1b[A", UP), ("\x1b[B", DOWN), ("\x1b[C", RIGHT), ("\x1b[D", LEFT),
                                      ("\x1bOA", UP), ("\x1b[1;5A", UP)])
def test_unix_arrows(seq, name):
    assert parse_unix(seq) == [KeyEvent(name)]


def test_unix_mixed_chunk():
    keys = parse_unix("w\x1b[Be\r\x7f\x03")
    assert [k.name for k in keys] == [CHAR, DOWN, CHAR, ENTER, BACKSPACE, CTRL_C]
    assert keys[0].char == "w" and keys[2].char == "e"


def test_lone_escape_and_unknown_sequences():
    assert parse_unix("\x1b") == [KeyEvent(ESC)]
    assert parse_unix("\x1b[15~") == []  # F5: ignored silently
    assert parse_unix("\x1bx") == [KeyEvent(ESC), KeyEvent(CHAR, "x")]


@pytest.mark.parametrize("prefix", ["\x00", "\xe0"])
@pytest.mark.parametrize("code,name", [("H", UP), ("P", DOWN), ("K", LEFT), ("M", RIGHT)])
def test_windows_arrows(prefix, code, name):
    assert parse_windows(prefix, code) == KeyEvent(name)


def test_windows_other_keys():
    assert parse_windows("\r") == KeyEvent(ENTER)
    assert parse_windows("\x1b") == KeyEvent(ESC)
    assert parse_windows("\x08") == KeyEvent(BACKSPACE)
    assert parse_windows("\x03") == KeyEvent(CTRL_C)
    assert parse_windows("e") == KeyEvent(CHAR, "e")
    assert parse_windows("\xe0", "Z") is None


def test_plain_lines():
    assert [k.char for k in parse_line("wwd")] == ["w", "w", "d"]
    assert parse_line("") == [KeyEvent(ENTER)]
    assert parse_line(" ESC ") == [KeyEvent(ESC)]


def test_key_serialisation():
    for key in (KeyEvent(UP), KeyEvent(CHAR, "e")):
        assert KeyEvent.from_dict(key.to_dict()) == key
    with pytest.raises(ValueError):
        KeyEvent.from_dict({"k": "NOPE"})
