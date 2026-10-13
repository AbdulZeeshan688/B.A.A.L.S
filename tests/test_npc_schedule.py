from conftest import advance_to


def test_tomas_waits_at_bus_stop_then_leaves(game):
    advance_to(game, "10:18")
    assert game.place_of("tomas") == "bus_stop"
    advance_to(game, "10:22")
    assert game.npc_gone("tomas")
    assert game.state.npcs["tomas"].present is False


def test_vera_reaches_cafe_by_0915(game):
    advance_to(game, "09:15")
    assert game.place_of("vera") == "cafe"


def test_vera_goes_to_town_hall_around_noon(game):
    advance_to(game, "12:40")
    assert game.place_of("vera") == "town_hall"


def test_kai_wanders_through_the_mill(game):
    seen = set()
    for _ in range(90):
        game.wait()
        seen.add(game.place_of("kai"))
    assert {"mill", "square", "bar_back"} <= seen


def test_npcs_only_stand_on_walkable_tiles(game):
    for _ in range(180):
        game.wait()
        for npc_id, st in game.state.npcs.items():
            if st.present:
                assert game.world.is_floor(st.pos) or game.world.char(st.pos) == "D", (npc_id, st.pos)


def test_people_wait_while_you_stand_next_to_them(game):
    from conftest import advance_to

    advance_to(game, "09:10")  # Vera is walking to the cafe
    vera = game.state.npcs["vera"]
    game.state.player.pos = (vera.pos[0] + 1, vera.pos[1])
    before = vera.pos
    for _ in range(5):
        game.wait()
    assert vera.pos == before, "she waits while you're beside her"
    for _ in range(3):
        game.wait()
    assert vera.pos != before, "but not forever"


def test_vera_does_not_stop_when_running_to_the_valve(game):
    vera = game.state.npcs["vera"]
    vera.goto = "valve_hut"
    game.state.player.pos = (vera.pos[0] + 1, vera.pos[1])
    before = vera.pos
    game.wait()
    assert vera.pos != before
