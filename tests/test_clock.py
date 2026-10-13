import pytest

from rerun.core.clock import DAY_TICKS, hhmm_to_tick, parse_hhmm, tick_to_hhmm, time_left_text


def test_day_is_180_ticks_of_two_minutes():
    assert DAY_TICKS == 180
    assert tick_to_hhmm(0) == "08:00"
    assert tick_to_hhmm(DAY_TICKS) == "14:00"


@pytest.mark.parametrize("text,tick", [("08:00", 0), ("09:30", 45), ("0930", 45), ("9.30", 45), ("14:00", 180)])
def test_time_round_trip(text, tick):
    assert hhmm_to_tick(text) == tick


def test_odd_minutes_round_up_to_next_tick():
    assert hhmm_to_tick("09:31") == 46


@pytest.mark.parametrize("bad", ["25:99", "abc", "", "12:60", "07:59", "14:02", "-1:00"])
def test_invalid_times_raise_value_error(bad):
    with pytest.raises(ValueError):
        hhmm_to_tick(bad)


def test_parse_and_time_left():
    assert parse_hhmm(" 13:05 ") == 13 * 60 + 5
    assert time_left_text(0) == "6h 00m"
    assert time_left_text(DAY_TICKS - 9) == "18m"
