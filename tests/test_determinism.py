import random

from rerun.solver.bot import Bot, play
from rerun.ui import keys as K
from rerun.ui.keys import KeyEvent, char_key


def test_same_route_same_seed_identical_state():
    a = play("sneaky", 11).game.state.snapshot()
    b = play("sneaky", 11).game.state.snapshot()
    assert a == b


def random_keys(seed: int, n: int) -> list[KeyEvent]:
    rng = random.Random(seed)
    pool = [KeyEvent(K.UP), KeyEvent(K.DOWN), KeyEvent(K.LEFT), KeyEvent(K.RIGHT), KeyEvent(K.ENTER),
            KeyEvent(K.ESC), KeyEvent(K.BACKSPACE), KeyEvent(K.TAB)]
    pool += [char_key(c) for c in "wasde.t1234567890:ngqy?!rhxz "]
    return [rng.choice(pool) for _ in range(n)]


def run_keys(seed: int, keys: list[KeyEvent]) -> dict:
    bot = Bot(seed=seed)
    for key in keys:
        if not bot.app.running or bot.app.game is None:
            bot.app.new_game(seed)
        bot.press(key)
        bot.app.render()  # every screen must render in every state
    return bot.app.game.state.snapshot() if bot.app.game else {}


def test_same_seed_same_keys_same_game():
    keys = random_keys(5, 1500)
    assert run_keys(42, keys) == run_keys(42, keys)


def test_fuzz_random_keys_never_crash():
    for seed in range(4):
        run_keys(seed, random_keys(seed, 2500))
