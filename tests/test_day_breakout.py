from fable_bot.strategies import Signal
from fable_bot.strategies.day_breakout import DAY_MS, DayBreakout

import pytest

HOUR_MS = 3_600_000
MIDNIGHT = (1_700_000_000_000 // DAY_MS) * DAY_MS


def day1(high: float = 110.0, low: float = 100.0, hours: int = 24) -> list[list[float]]:
    """A full previous day ranging between low and high."""
    return [[float(MIDNIGHT + i * HOUR_MS), 105.0, high, low, 105.0, 10.0]
            for i in range(hours)]


def day2(closes: list[float], open_: float = 105.0) -> list[list[float]]:
    return [[float(MIDNIGHT + DAY_MS + i * HOUR_MS), open_, c, c, c, 10.0]
            for i, c in enumerate(closes)]


def test_buys_when_price_clears_the_trigger():
    # Trigger = open 105 + 0.5 * range 10 = 110.
    candles = day1() + day2([106.0, 108.0, 111.0])
    assert DayBreakout(range_mult=0.5).signal(candles) is Signal.BUY


def test_holds_below_the_trigger():
    candles = day1() + day2([106.0, 108.0, 109.5])
    assert DayBreakout(range_mult=0.5).signal(candles) is Signal.HOLD


def test_flattens_on_the_last_candle_of_the_day():
    candles = day1() + day2([111.0] * 24)  # breakout happened, but the day is over
    assert DayBreakout(range_mult=0.5).signal(candles) is Signal.SELL


def test_holds_without_a_complete_previous_day():
    # Above the would-be trigger, but yesterday's range is only 10 candles deep.
    candles = day1(hours=10) + day2([106.0] * 20 + [111.0])
    assert DayBreakout(range_mult=0.5).signal(candles) is Signal.HOLD


def test_trend_filter_blocks_counter_trend_breakouts():
    # Price broke out today, but sits below a long SMA anchored by a high past.
    past = [[float(MIDNIGHT - DAY_MS + i * HOUR_MS), 200.0, 200.0, 200.0, 200.0, 10.0]
            for i in range(24)]
    candles = past + day1() + day2([106.0, 108.0, 111.0])
    assert DayBreakout(range_mult=0.5, trend_period=48).signal(candles) is Signal.HOLD


def test_rejects_bad_params():
    with pytest.raises(ValueError):
        DayBreakout(range_mult=0.0)
    with pytest.raises(ValueError):
        DayBreakout(trend_period=-1)
