"""Record and play back key presses. Same seed + same keys = same game.

File format (JSON lines):
    {"rerun_replay": 1, "seed": 42, "pack": "marrow"}
    {"k": "UP"}
    {"k": "CHAR", "c": "e"}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from ..ui.keys import KeyEvent

REPLAY_VERSION = 1


class ReplayError(ValueError):
    """The replay file can't be used."""


class Recorder:
    """Appends each key to a replay file as it is pressed."""

    def __init__(self, path: Path, seed: int, pack: str) -> None:
        self.path = path
        self._file: TextIO = path.open("w", encoding="utf-8")
        self._write({"rerun_replay": REPLAY_VERSION, "seed": seed, "pack": pack})

    def record(self, key: KeyEvent) -> None:
        """Write one key."""
        self._write(key.to_dict())

    def close(self) -> None:
        """Flush and close the file."""
        if not self._file.closed:
            self._file.close()

    def _write(self, obj: dict) -> None:
        self._file.write(json.dumps(obj) + "\n")
        self._file.flush()


def load_replay(path: Path) -> tuple[int, str, list[KeyEvent]]:
    """Read a replay file -> (seed, pack, keys). Raises ReplayError with a clear reason."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ReplayError(f"cannot read {path}: {exc.strerror or exc}") from None
    if not lines:
        raise ReplayError(f"{path} is empty")
    try:
        header = json.loads(lines[0])
        if header.get("rerun_replay") != REPLAY_VERSION or not isinstance(header.get("seed"), int):
            raise ReplayError(f"{path} is not a RERUN replay (version {REPLAY_VERSION})")
        keys = [KeyEvent.from_dict(json.loads(line)) for line in lines[1:] if line.strip()]
    except (json.JSONDecodeError, AttributeError, ValueError) as exc:
        if isinstance(exc, ReplayError):
            raise
        raise ReplayError(f"{path} is damaged: {exc}") from None
    return header["seed"], str(header.get("pack", "marrow")), keys
