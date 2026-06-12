"""Trend-following: buy when the fast SMA crosses above the slow SMA, sell on the reverse cross."""

from fable_bot.strategies.base import Signal, Strategy, closes, sma


class SmaCrossover(Strategy):
    def __init__(self, fast_period: int = 9, slow_period: int = 21):
        if fast_period >= slow_period:
            raise ValueError("fast_period must be smaller than slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period

    @property
    def min_candles(self) -> int:
        return self.slow_period + 1

    def signal(self, candles: list[list[float]]) -> Signal:
        if len(candles) < self.min_candles:
            return Signal.HOLD
        prices = closes(candles)
        fast_now = sma(prices, self.fast_period)
        slow_now = sma(prices, self.slow_period)
        fast_prev = sma(prices[:-1], self.fast_period)
        slow_prev = sma(prices[:-1], self.slow_period)

        if fast_prev <= slow_prev and fast_now > slow_now:
            return Signal.BUY
        if fast_prev >= slow_prev and fast_now < slow_now:
            return Signal.SELL
        return Signal.HOLD
