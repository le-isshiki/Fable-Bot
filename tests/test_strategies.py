import pytest

from fable_bot.strategies import STRATEGIES, Signal, build_strategy
from fable_bot.strategies.rsi_reversion import RsiReversion, rsi
from fable_bot.strategies.sma_crossover import SmaCrossover


def make_candles(closes: list[float]) -> list[list[float]]:
    return [[float(i), c, c, c, c, 1.0] for i, c in enumerate(closes)]


class TestSmaCrossover:
    def test_buy_on_upward_cross(self):
        # Long decline then a sharp rally pushes the fast SMA above the slow.
        closes = [100 - i for i in range(30)] + [75, 85, 95, 105, 115, 125]
        strat = SmaCrossover(fast_period=3, slow_period=10)
        signals = [strat.signal(make_candles(closes[: i + 1])) for i in range(len(closes))]
        assert Signal.BUY in signals

    def test_sell_on_downward_cross(self):
        closes = [100 + i for i in range(30)] + [125, 115, 105, 95, 85, 75]
        strat = SmaCrossover(fast_period=3, slow_period=10)
        signals = [strat.signal(make_candles(closes[: i + 1])) for i in range(len(closes))]
        assert Signal.SELL in signals

    def test_hold_with_insufficient_history(self):
        strat = SmaCrossover(fast_period=3, slow_period=10)
        assert strat.signal(make_candles([100.0] * 5)) is Signal.HOLD

    def test_rejects_inverted_periods(self):
        with pytest.raises(ValueError):
            SmaCrossover(fast_period=20, slow_period=10)


class TestRsiReversion:
    def test_rsi_bounds(self):
        rising = [float(i) for i in range(1, 50)]
        assert rsi(rising, 14) == 100.0
        falling = [float(i) for i in range(50, 1, -1)]
        assert rsi(falling, 14) < 5.0

    def test_buy_when_oversold(self):
        closes = [100.0] * 30 + [100 - i * 2 for i in range(1, 15)]
        strat = RsiReversion(period=14)
        assert strat.signal(make_candles(closes)) is Signal.BUY

    def test_sell_when_overbought(self):
        closes = [100.0] * 30 + [100 + i * 2 for i in range(1, 15)]
        strat = RsiReversion(period=14)
        assert strat.signal(make_candles(closes)) is Signal.SELL


def test_registry_builds_all_strategies():
    for name in STRATEGIES:
        strat = build_strategy(name, {})
        assert strat.min_candles > 0


def test_registry_rejects_unknown_name():
    with pytest.raises(ValueError, match="Unknown strategy"):
        build_strategy("does_not_exist", {})
