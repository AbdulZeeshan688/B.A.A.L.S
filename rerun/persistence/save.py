"""Save file: atomic writes, versioning, and recovery from anything broken.

The game must never crash because of a save file. Anything unreadable is
moved aside to save.json.bad and the player gets a one-line notice.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

SAVE_VERSION = 1
SAVE_NAME = "save.json"


def save_dir() -> Path:
    """Where RERUN keeps its files. RERUN_HOME overrides (used by tests)."""
    override = os.environ.get("RERUN_HOME")
    if override:
        return Path(override)
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "rerun"
    return Path.home() / ".rerun"


@dataclass
class Settings:
    """Player preferences (persist across runs)."""

    color: bool = True
    ascii_only: bool = False
    reduced_motion: bool = False
    ghost: bool = True

    @classmethod
    def from_dict(cls, data: object) -> "Settings":
        """Tolerant loader: unknown keys ignored, bad values defaulted."""
        if not isinstance(data, dict):
            return cls()
        defaults = cls()
        return cls(**{k: data[k] if isinstance(data.get(k), bool) else getattr(defaults, k)
                      for k in asdict(defaults)})


@dataclass
class RunData:
    """An unfinished run: knowledge and stats, resumed at 08:00."""

    seed: int
    loop: int
    notebook: dict
    stats: dict
    ghost: list = field(default_factory=list)


@dataclass
class SaveData:
    """Everything in save.json."""

    settings: Settings = field(default_factory=Settings)
    best_loops: int | None = None
    run: RunData | None = None

    def to_dict(self) -> dict:
        """Serialise with a version tag."""
        return {"version": SAVE_VERSION, "settings": asdict(self.settings), "best_loops": self.best_loops,
                "run": asdict(self.run) if self.run else None}


class SaveError(ValueError):
    """The save file exists but can't be used."""


def parse_save(raw: object) -> SaveData:
    """Validate decoded JSON. Raises SaveError with a short reason."""
    if not isinstance(raw, dict):
        raise SaveError("not a save file")
    if raw.get("version") != SAVE_VERSION:
        raise SaveError(f"save is from version {raw.get('version')!r}, this game uses {SAVE_VERSION}")
    best = raw.get("best_loops")
    run = None
    if raw.get("run") is not None:
        r = raw["run"]
        if not (isinstance(r, dict) and isinstance(r.get("seed"), int) and isinstance(r.get("loop"), int)
                and r["loop"] >= 1 and isinstance(r.get("notebook"), dict) and isinstance(r.get("stats"), dict)):
            raise SaveError("run data is damaged")
        ghost = [tuple(p) for p in r.get("ghost", []) if isinstance(p, list) and len(p) == 2]
        run = RunData(r["seed"], r["loop"], r["notebook"], r["stats"], ghost)
    return SaveData(Settings.from_dict(raw.get("settings")), best if isinstance(best, int) else None, run)


class SaveStore:
    """Loads and saves save.json in one folder. Disabled stores do nothing."""

    def __init__(self, directory: Path | None = None, enabled: bool = True) -> None:
        self.directory = directory or save_dir()
        self.enabled = enabled

    @property
    def path(self) -> Path:
        """Full path to save.json."""
        return self.directory / SAVE_NAME

    def load(self) -> tuple[SaveData, str | None]:
        """Return (data, notice). Never raises; a bad file is moved aside."""
        if not self.enabled or not self.path.exists():
            return SaveData(), None
        try:
            text = self.path.read_text(encoding="utf-8")
            return parse_save(json.loads(text)), None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, SaveError, TypeError, ValueError) as exc:
            reason = exc if isinstance(exc, SaveError) else "file is corrupt"
            moved = self._quarantine()
            where = f" (kept as {moved.name})" if moved else ""
            return SaveData(), f"Save file couldn't be used: {reason}. Starting fresh{where}."

    def save(self, data: SaveData) -> str | None:
        """Atomically write the save. Returns an error message instead of raising."""
        if not self.enabled:
            return None
        tmp = self.path.with_name(SAVE_NAME + ".tmp")
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data.to_dict(), indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
            return None
        except OSError as exc:
            return f"Could not save ({exc.strerror or exc})."

    def _quarantine(self) -> Path | None:
        bad = self.path.with_name(SAVE_NAME + ".bad")
        try:
            os.replace(self.path, bad)
            return bad
        except OSError:
            return None
