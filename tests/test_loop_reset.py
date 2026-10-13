from conftest import advance_to

from rerun.core.state import Outcome


def test_flood_at_1400_then_reset_keeps_only_notebook(game):
    start = game.state.player.pos
    game.state.notebook.learn("gauge_reading", 1)
    game.state.player.items.add("key")
    game.state.flags.add("vera_convinced")
    game.state.npcs["vera"].trust = 5
    game.move(-1, 0)
    advance_to(game, "14:00")
    assert game.state.outcome == Outcome.FLOODED
    assert game.knows("dam_breaks")
    game.next_loop()
    s = game.state
    assert s.loop == 2 and s.tick == 0 and s.outcome is None
    assert s.player.pos == start and not s.player.items and not s.flags
    assert s.npcs["vera"].trust == 50
    assert game.knows("gauge_reading") and game.knows("dam_breaks")
    assert s.stats.outcomes == ["~"]
    assert s.ghost, "last loop's path becomes the ghost trail"


def test_skip_cannot_jump_past_the_flood(game):
    for _ in range(20):
        if game.state.outcome:
            break
        assert game.skip_to("14:00") is None
    assert game.state.outcome == Outcome.FLOODED
    assert game.state.tick == 180


def test_skip_rejects_bad_input(game):
    assert "not a time" in game.skip_to("abc")
    assert "not a real time" in game.skip_to("25:99")
    advance_to(game, "10:00")
    assert "already" in game.skip_to("09:00")
    assert game.state.tick == 60


def test_restart_counts_as_a_lost_loop(game):
    game.restart_loop()
    assert game.state.outcome == Outcome.RESTARTED
    game.next_loop()
    assert game.state.stats.outcomes == ["~"]


def test_actions_after_loop_end_do_nothing(game):
    game.restart_loop()
    tick = game.state.tick
    assert game.move(1, 0) is False
    game.wait()
    game.shout()
    assert game.state.tick == tick


def test_far_away_bus_does_not_interrupt_a_skip(game):
    game.state.player.pos = (1, 4)  # beside the gauge, far from the bus stop
    game.state.npcs["kai"].wander_picks = {k: (40, 13) for k in range(20)}  # keep Kai away
    game.skip_to("09:30")
    game.skip_to("11:00")
    assert game.clock() == "11:00"


def test_interrupted_skip_explains_itself_and_remembers_target(game):
    game.state.player.pos = (35, 15)  # at the bus stop: Tomas walks right up
    game.skip_to("11:00")
    assert game.clock() < "11:00"
    texts = [e.text for e in game.drain_events()]
    assert any("Skip paused" in t and "Press T again" in t for t in texts)
    assert game.skip_paused == "11:00"
