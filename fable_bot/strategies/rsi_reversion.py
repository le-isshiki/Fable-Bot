"""Mean reversion: buy when RSI drops below the oversold level, sell when it rises above overbought."""

from fable_bot.strategies.base import Signal, Strategy, closes


def rsi(prices: list[float], period: int) -> float:
    """Wilder-smoothed RSI of the latest price."""
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


class RsiReversion(Strategy):
    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        if not 0 < oversold < overbought < 100:
            raise ValueError("require 0 < oversold < overbought < 100")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    @property
    def min_candles(self) -> int:
        return self.period * 3

    def signal(self, candles: list[list[float]]) -> Signal:
        if len(candles) < self.min_candles:
            return Signal.HOLD
        value = rsi(closes(candles), self.period)
        if value < self.oversold:
            return Signal.BUY
        if value > self.overbought:
            return Signal.SELL
        return Signal.HOLD
