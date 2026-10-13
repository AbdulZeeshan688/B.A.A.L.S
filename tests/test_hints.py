"""The GOAL line must always point at the next useful step."""

from conftest import advance_to


def test_hint_follows_the_honest_route(game):
    assert "Vera (V)" in game.current_hint()
    game.state.notebook.learn("dam_breaks", 1)
    assert "gauge" in game.current_hint()
    game.state.notebook.learn("gauge_rising", 1)
    assert "11:00" in game.current_hint()
    game.state.notebook.learn("gauge_reading", 1)
    assert "Tell Vera" in game.current_hint()
    game.state.notebook.learn("valve_exists", 1)
    assert "Ilse" in game.current_hint()
    game.state.notebook.learn("key_with_tomas", 1)
    assert "10:20 bus" in game.current_hint()
    game.state.player.items.add("key")
    assert "give her the key" in game.current_hint()
    game.state.flags.add("vera_has_key")
    assert "14:00" in game.current_hint()


def test_hint_when_tomas_is_gone(game):
    game.state.notebook.learn("key_with_tomas", 1)
    advance_to(game, "10:22")
    assert "Too late" in game.current_hint()
    game.state.notebook.learn("back_door", 1)
    assert "back door" in game.current_hint()


def test_every_hint_fits_the_goal_line(content):
    for hint in content.hints:
        assert len(hint.text) <= 70, hint.text
    assert content.hints[-1].cond is None, "last hint must be a catch-all"


def test_hints_can_be_switched_off(isolated_home):
    from test_app import make_app, new_game, text

    app = make_app(isolated_home)
    new_game(app)
    assert "GOAL" in text(app)
    app.settings.hints = False
    assert "GOAL" not in text(app)


def test_goal_points_at_the_right_thing(game):
    assert game.goal_position() == game.state.npcs["vera"].pos
    game.state.notebook.learn("dam_breaks", 1)
    gauge = next(o.pos for o in game.content.objects if o.id == "gauge")
    assert game.goal_position() == gauge


def test_learning_a_key_fact_announces_the_unlock(game):
    game.state.npcs["ilse"].pos = game.world.region("pharmacy").spot(0)
    game.state.notebook.learn("valve_exists", 1)
    game.choose("ilse", "oskar")
    texts = [e.text for e in game.drain_events()]
    assert any("New secret" in t and "Tomas" in t for t in texts)
