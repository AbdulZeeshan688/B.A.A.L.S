"""Shared fixtures. Every test runs with RERUN_HOME in a temp dir, so nothing touches ~/.rerun."""

from __future__ import annotations

import pytest

from rerun.core.content import load_content
from rerun.core.engine import Game


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Keep all game files inside a temp folder."""
    home = tmp_path / "rerun_home"
    monkeypatch.setenv("RERUN_HOME", str(home))
    return home


@pytest.fixture(scope="session")
def content():
    """The Marrow story pack (loaded once)."""
    return load_content()


@pytest.fixture
def game(content):
    """A fresh game, loop 1, 08:00."""
    g = Game(content, seed=1)
    g.drain_events()
    return g


def advance_to(game: Game, hhmm: str) -> None:
    """Wait tick by tick until the clock shows hhmm (no early stops)."""
    from rerun.core.clock import hhmm_to_tick

    target = hhmm_to_tick(hhmm)
    while game.state.tick < target and not game.state.outcome:
        game.wait()
