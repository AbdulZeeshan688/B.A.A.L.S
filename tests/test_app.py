"""Headless tests of the whole app: screens, flow, saving."""

from pathlib import Path

from rerun.app import App, Options
from rerun.persistence.save import SaveStore
from rerun.ui import keys as K
from rerun.ui.keys import KeyEvent, char_key
from rerun.ui.screens.endings import LoopEndScreen, WinScreen, resize_canvas
from rerun.ui.screens.game import GameScreen
from rerun.ui.screens.menus import PromptScreen, TitleScreen
from rerun.ui.screens.notebook import NotebookScreen
from rerun.ui.terminal import HeadlessIO
from rerun.ui.theme import Theme


def make_app(home: Path, **opts) -> App:
    options = Options(reduced_motion=True, seed=1, **opts)
    app = App(options, HeadlessIO(), SaveStore(home), Theme())
    app.start()
    return app


def press(app, *keys):
    for key in keys:
        app.handle_key(char_key(key) if isinstance(key, str) else key)
        app.render()


def new_game(app):
    """Title -> New game -> skip the story intro."""
    press(app, "1")
    from rerun.ui.screens.intro import IntroScreen

    assert isinstance(app.stack[-1], IntroScreen)
    press(app, KeyEvent(K.ESC))


def text(app) -> str:
    return "\n".join(app.render().plain_lines())


def test_title_new_game_and_quit_saves(isolated_home):
    app = make_app(isolated_home)
    assert isinstance(app.stack[-1], TitleScreen)
    new_game(app)
    assert isinstance(app.stack[-1], GameScreen)
    press(app, KeyEvent(K.LEFT), "q", "y")
    assert isinstance(app.stack[-1], TitleScreen)
    assert (isolated_home / "save.json").exists()
    assert "Continue" in text(app)


def test_game_screen_shows_hud(isolated_home):
    app = make_app(isolated_home)
    new_game(app)
    screen = text(app)
    for expected in ("RERUN", "loop 1", "08:00", "FLOOD in 6h 00m", "NOTEBOOK", "You: the Bus Stop", "[E] talk/use"):
        assert expected in screen
    assert "@" in screen


def test_skip_prompt_handles_bad_input_then_works(isolated_home):
    app = make_app(isolated_home)
    new_game(app)
    press(app, "t", "a", "b", "c", KeyEvent(K.ENTER))
    assert isinstance(app.stack[-1], PromptScreen) and "not a time" in text(app)
    press(app, KeyEvent(K.ESC), "t", "0", "9", ":", "0", "0", KeyEvent(K.ENTER))
    assert app.game.state.tick > 0


def test_flood_screen_then_next_loop(isolated_home):
    app = make_app(isolated_home)
    new_game(app)
    for _ in range(30):
        if isinstance(app.stack[-1], LoopEndScreen):
            break
        press(app, "t", "1", "4", ":", "0", "0", KeyEvent(K.ENTER))
    assert isinstance(app.stack[-1], LoopEndScreen)
    assert "THE DAM BROKE" in text(app)
    press(app, "n")
    assert isinstance(app.stack[-1], NotebookScreen)
    assert "At 14:00 the dam breaks" in text(app)
    press(app, KeyEvent(K.ESC), KeyEvent(K.ENTER))
    assert app.game.state.loop == 2
    saved = SaveStore(isolated_home).load()[0]
    assert saved.run.loop == 2 and "dam_breaks" in saved.run.notebook


def test_continue_restores_notebook(isolated_home):
    app = make_app(isolated_home)
    new_game(app)
    app.game.state.notebook.learn("gauge_reading", 1)
    press(app, "q", "y")
    app2 = make_app(isolated_home)
    press(app2, "1")  # Continue
    assert app2.game.knows("gauge_reading")


def test_win_clears_run_and_records_best(isolated_home):
    from rerun.solver.bot import Bot, honest_route

    bot = Bot(seed=1)
    bot.app.store = SaveStore(isolated_home)
    honest_route(bot)
    assert isinstance(bot.screen, WinScreen)
    screen = "\n".join(bot.app.render().plain_lines())
    assert "MARROW IS SAFE" in screen and "RERUN #0001  SAVED in 2 loops  ~*" in screen
    saved = SaveStore(isolated_home).load()[0]
    assert saved.run is None and saved.best_loops == 2


def test_corrupt_save_shows_notice_not_crash(isolated_home):
    isolated_home.mkdir(parents=True)
    (isolated_home / "save.json").write_text("garbage")
    app = make_app(isolated_home)
    new_game(app)
    assert "Starting fresh" in text(app)


def test_talk_overlay_and_from_notes_marker(isolated_home):
    app = make_app(isolated_home)
    new_game(app)
    game = app.game
    game.state.notebook.learn("key_with_tomas", 1)
    game.state.player.pos = (5, 9)  # next to Tomas in the bar at 08:00
    press(app, "e")
    screen = text(app)
    assert "TOMAS" in screen and "[from notes]" in screen
    press(app, KeyEvent(K.ESC))
    assert isinstance(app.stack[-1], GameScreen)


def test_resize_screen_text():
    lines = "\n".join(resize_canvas(70, 20, 80, 24).plain_lines())
    assert "at least 80x24" in lines and "now: 70x20" in lines
    resize_canvas(1, 1, 80, 24)  # absurdly small must not crash


def test_ascii_mode_renders_only_ascii(isolated_home):
    app = make_app(isolated_home, ascii=True)
    press(app, "1")
    from rerun.ui.renderer import Renderer

    out = []
    Renderer(app.theme, out.append).draw(app.render(), 80, 24)
    assert all(ord(ch) < 128 for ch in "".join(out))


def test_mono_mode_has_no_colour_codes(isolated_home):
    app = make_app(isolated_home, mono=True)
    press(app, "1")
    from rerun.ui.renderer import Renderer

    out = []
    Renderer(app.theme, out.append).draw(app.render(), 80, 24)
    import re

    params = [int(n) for sgr in re.findall(r"\x1b\[([0-9;]*)m", "".join(out)) for n in sgr.split(";") if n]
    assert not [n for n in params if 30 <= n <= 49 or 90 <= n <= 107], "colour codes found in mono mode"


def test_daily_run_does_not_touch_saved_run(isolated_home):
    app = make_app(isolated_home)
    new_game(app)
    app.game.state.notebook.learn("gauge_reading", 1)
    press(app, "q", "y")
    daily = make_app(isolated_home, daily=True)
    assert isinstance(daily.stack[-1], GameScreen) and not daily.game.knows("gauge_reading")
    press(daily, KeyEvent(K.LEFT), "q", "y")
    assert "gauge_reading" in SaveStore(isolated_home).load()[0].run.notebook


def test_intro_pages_then_game(isolated_home):
    app = make_app(isolated_home)
    press(app, "1")
    assert "THIS IS MARROW" in text(app)
    press(app, KeyEvent(K.ENTER))
    assert "THE DAM BREAKS" in text(app)
    press(app, KeyEvent(K.LEFT))
    assert "THIS IS MARROW" in text(app)
    press(app, KeyEvent(K.ENTER), KeyEvent(K.ENTER), KeyEvent(K.ENTER))
    assert "YOUR MISSION" in text(app)
    press(app, KeyEvent(K.ENTER))
    assert isinstance(app.stack[-1], GameScreen)


def test_goal_marker_and_directions(isolated_home):
    app = make_app(isolated_home)
    new_game(app)
    screen = text(app)
    assert "Go: V Vera, 25 steps W" in screen
    assert "▼" in screen
