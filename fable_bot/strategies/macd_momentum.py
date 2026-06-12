"""Momentum: buy when the MACD line crosses above its signal line, sell on the cross below."""

from fable_bot.strategies.base import Signal, Strategy, closes


def ema_series(values: list[float], period: int) -> list[float]:
    k = 2.0 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


class MacdMomentum(Strategy):
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        if fast_period >= slow_period:
            raise ValueError("fast_period must be smaller than slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    @property
    def min_candles(self) -> int:
        # EMAs need warm-up beyond their period to converge.
        return self.slow_period + self.signal_period + 10

    def signal(self, candles: list[list[float]]) -> Signal:
        if len(candles) < self.min_candles:
            return Signal.HOLD
        prices = closes(candles)
        fast = ema_series(prices, self.fast_period)
        slow = ema_series(prices, self.slow_period)
        macd = [f - s for f, s in zip(fast, slow)]
        sig = ema_series(macd, self.signal_period)

        above_now = macd[-1] > sig[-1]
        above_prev = macd[-2] > sig[-2]
        if above_now and not above_prev:
            return Signal.BUY
        if not above_now and above_prev:
            return Signal.SELL
        return Signal.HOLD
