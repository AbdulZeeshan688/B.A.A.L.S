import subprocess
import sys


def run(*args, stdin=""):
    return subprocess.run([sys.executable, "-m", "rerun", *args], input=stdin, capture_output=True, text=True,
                          timeout=60)


def test_version():
    assert "rerun" in run("--version").stdout


def test_bad_replay_exits_2(tmp_path):
    bad = tmp_path / "x.rec"
    bad.write_text("nope")
    result = run("--replay", str(bad))
    assert result.returncode == 2 and "damaged" in result.stderr


def test_record_and_replay_together_rejected(tmp_path):
    assert run("--record", "a", "--replay", "b").returncode == 2


def test_plain_mode_is_playable_without_a_tty(isolated_home):
    # No terminal: the game falls back to plain mode. New game, walk, open notebook, quit.
    script = "1\nwww\nn\nesc\nq\ny\n5\n"
    result = run("--new", "--seed", "3", stdin=script)
    assert result.returncode == 0, result.stderr
    assert "switching to --plain" in result.stdout
    assert "NOTEBOOK" in result.stdout and "Thanks for playing" in result.stdout
    assert (isolated_home / "save.json").exists()


def test_end_of_input_saves_and_exits_cleanly(isolated_home):
    result = run("--new", stdin="1\nwww\n")
    assert result.returncode == 130
    assert "notebook is saved" in result.stdout


def test_unexpected_crash_is_logged_and_reported(isolated_home):
    code = ("import rerun.app as a\n"
            "a.App.run = lambda self: 1 / 0\n"
            "from rerun.cli import main\n"
            "raise SystemExit(main(['--plain', '--new']))\n")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert result.returncode == 1
    assert "closed safely" in result.stderr and "crash.log" in result.stderr
    log = (isolated_home / "crash.log").read_text()
    assert "ZeroDivisionError" in log
