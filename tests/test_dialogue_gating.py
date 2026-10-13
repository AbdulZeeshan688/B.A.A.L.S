def topic_ids(game, npc_id):
    return [t.id for t in game.topics(npc_id)]


def test_tomas_key_topic_needs_the_fact(game):
    assert "tab" not in topic_ids(game, "tomas")
    game.state.notebook.learn("key_with_tomas", 1)
    assert "tab" in topic_ids(game, "tomas")
    assert next(t for t in game.topics("tomas") if t.id == "tab").from_notes


def test_tomas_gives_key_once(game):
    game.state.notebook.learn("key_with_tomas", 1)
    reply = game.choose("tomas", "tab")
    assert "Take it" in reply
    assert game.has_item("key")
    assert "tab" not in topic_ids(game, "tomas")


def test_vera_needs_gauge_before_key_matters(game):
    game.state.player.items.add("key")
    assert "Why would I need" in game.choose("vera", "give_key")
    game.state.notebook.learn("gauge_reading", 1)
    game.choose("vera", "gauge")
    assert game.knows("valve_exists")
    game.choose("vera", "give_key")
    assert game.state.npcs["vera"].goto == "valve_hut"
    assert not game.has_item("key")


def test_low_trust_blocks_vera(game):
    game.state.notebook.learn("gauge_reading", 1)
    game.state.npcs["vera"].trust = 20
    assert "pestering" in game.choose("vera", "gauge")
    assert not game.knows("valve_exists")


def test_kai_only_tells_secret_at_the_mill(game):
    assert "Ask me at the Mill" in game.choose("kai", "secret")
    game.state.npcs["kai"].pos = game.world.region("mill").spot(0)
    game.choose("kai", "secret")
    assert game.knows("back_door")


def test_gauge_reading_changes_after_eleven(game):
    assert "8.7" in game.inspect("gauge")
    assert game.knows("gauge_rising") and not game.knows("gauge_reading")
    from conftest import advance_to
    advance_to(game, "11:00")
    assert "9.4" in game.inspect("gauge")
    assert game.knows("gauge_reading")


def test_talking_too_much_lowers_trust(game):
    for _ in range(5):
        game.talk("ilse")
    assert game.state.npcs["ilse"].trust < 50


def test_unknown_topic_is_harmless(game):
    assert game.choose("vera", "does_not_exist") == "They don't follow."
