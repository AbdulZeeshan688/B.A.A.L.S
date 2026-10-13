from conftest import advance_to

from rerun.core import rumours
from rerun.core.rng import GameRng
from rerun.core.state import Outcome


def break_in(game, witness_pos):
    """Learn the back door, wait for Tomas to leave, step through it with Kai at witness_pos."""
    game.state.notebook.learn("back_door", 1)
    advance_to(game, "10:22")
    door = next(d for d in game.content.doors if d.id == "bar_back")
    game.state.player.pos = (door.pos[0], door.pos[1] - 1)
    game.state.npcs["kai"].pos = witness_pos
    game.state.npcs["kai"].wander_picks = {k: witness_pos for k in range(20)}
    assert game.move(0, 1), "back door should open after Tomas leaves"


def test_locked_back_door_without_fact(game):
    advance_to(game, "10:22")
    door = next(d for d in game.content.doors if d.id == "bar_back")
    game.state.player.pos = (door.pos[0], door.pos[1] - 1)
    assert game.move(0, 1) is False
    assert any("locked" in e.text for e in game.drain_events())


def test_seen_break_in_starts_rumour_that_reaches_vera(game):
    break_in(game, (4, 7))
    assert game.has_rumour("kai", "thief")
    assert game.state.stats.rumours_started == 1
    # Put Kai and Vera side by side; seeded 50% gossip must spread within a few ticks.
    game.state.npcs["kai"].pos = game.state.npcs["vera"].pos
    rng = GameRng(1, "test")
    for _ in range(10):
        rumours.spread(game.state, game.content, rng, lambda pos: True)
        if game.has_rumour("vera", "thief"):
            break
    assert game.has_rumour("vera", "thief")
    game.state.notebook.learn("gauge_reading", 1)
    assert "thieves" in game.choose("vera", "gauge")
    assert not game.has_flag("vera_convinced")
    assert game.knows("vera_thieves")


def test_unseen_break_in_starts_no_rumour(game):
    break_in(game, (40, 13))
    assert not any(st.rumours for st in game.state.npcs.values())


def test_shouting_near_the_mayor_gets_you_arrested(game):
    game.state.player.pos = game.state.npcs["mayor"].pos
    game.shout()
    assert game.state.outcome == Outcome.ARRESTED


def test_shouting_alone_is_harmless(game):
    game.state.player.pos = (57, 15)
    game.shout()
    assert game.state.outcome is None
    assert any("Nobody" in e.text for e in game.drain_events())


def test_kai_on_his_bar_back_spots_can_see_the_back_door(game):
    door = next(d for d in game.content.doors if d.id == "bar_back")
    for spot in game.world.region("bar_back").spots:
        assert game.world.line_of_sight(spot, door.pos)


def test_walls_block_sight(game):
    assert not game.world.line_of_sight((5, 10), (5, 14))  # inside the bar vs the square
