import pytest

from rerun.extras.replay import ReplayError, load_replay
from rerun.solver.bot import Bot, play


def test_recorded_demo_replays_to_same_result(tmp_path):
    path = tmp_path / "demo.rec"
    recorded = play("demo", 9, record=path)
    seed, pack, keys = load_replay(path)
    assert seed == 9 and pack == "marrow" and len(keys) == recorded.presses

    replayed = Bot(seed=seed)
    for key in keys:
        replayed.press(key)
    assert replayed.won
    assert replayed.game.state.snapshot() == recorded.game.state.snapshot()


@pytest.mark.parametrize("body", ["", "not json\n", '{"rerun_replay": 99, "seed": 1}\n',
                                  '{"rerun_replay": 1, "seed": 1}\n{"k": "WARP"}\n'])
def test_bad_replays_raise_clear_errors(tmp_path, body):
    path = tmp_path / "bad.rec"
    path.write_text(body)
    with pytest.raises(ReplayError):
        load_replay(path)


def test_missing_replay(tmp_path):
    with pytest.raises(ReplayError):
        load_replay(tmp_path / "nope.rec")
