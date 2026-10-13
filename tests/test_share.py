from datetime import date

from rerun.extras.share import daily_seed, run_id, share_line, time_used_text


def test_share_line_has_no_spoilers():
    line = share_line(4821, ["~", "~", "^", "*"])
    assert line == "RERUN #4821  SAVED in 4 loops  ~~^*"
    for secret in ("Tomas", "key", "valve", "gauge"):
        assert secret not in line


def test_daily_seed_and_id():
    seed = daily_seed(date(2026, 10, 14))
    assert seed == 20261014
    assert run_id(seed) == "Daily 2026-10-14"
    assert run_id(7) == "#0007"


def test_time_used():
    assert time_used_text(180) == "6h 00m"
