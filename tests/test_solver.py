import pytest

from rerun.solver.bot import play


@pytest.mark.parametrize("route", ["honest", "sneaky", "demo"])
@pytest.mark.parametrize("seed", [1, 7, 2026])
def test_routes_win(route, seed):
    bot = play(route, seed)
    assert bot.won, f"{route} route failed on seed {seed}"
    assert bot.game.state.stats.outcomes[-1] == "*"


def test_do_nothing_player_floods_every_loop():
    bot = play("idle", 3)
    assert bot.game.state.stats.outcomes == ["~", "~", "~"]
    assert not bot.won
