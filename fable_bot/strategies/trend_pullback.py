"""Buy short-term pullbacks within an established uptrend; stand aside otherwise.

Rationale: the two classic single-indicator families fail in opposite ways.
Trend-followers (SMA/MACD crossovers) get chopped to death in ranging
markets — every whipsaw pays fees. Mean-reverters (RSI oversold) happily
buy into a genuine collapse. Requiring BOTH conditions — price above a slow
SMA (the trend exists) and a depressed short-term RSI (a local discount) —
buys dips with the prevailing wind at their back, and never holds a long
while price is below trend.

Exits: RSI recovering above exit_rsi (the pullback resolved) or price
closing below the trend SMA (the premise is gone).
"""

from fable_bot.strategies.base import Signal, Strategy, closes, sma
from fable_bot.strategies.rsi_reversion import rsi


class TrendPullback(Strategy):
    def __init__(self, trend_period: int = 100, rsi_period: int = 14,
                 entry_rsi: float = 40.0, exit_rsi: float = 65.0):
        if not 0 < entry_rsi < exit_rsi < 100:
            raise ValueError("require 0 < entry_rsi < exit_rsi < 100")
        if trend_period <= rsi_period:
            raise ValueError("trend_period must exceed rsi_period")
        self.trend_period = trend_period
        self.rsi_period = rsi_period
        self.entry_rsi = entry_rsi
        self.exit_rsi = exit_rsi

    @property
    def min_candles(self) -> int:
        return max(self.trend_period + 1, self.rsi_period * 3)

    def signal(self, candles: list[list[float]]) -> Signal:
        if len(candles) < self.min_candles:
            return Signal.HOLD
        prices = closes(candles)
        trend = sma(prices, self.trend_period)
        if prices[-1] < trend:
            # Downtrend or trend break: exit any long, never open one.
            return Signal.SELL
        momentum = rsi(prices, self.rsi_period)
        if momentum < self.entry_rsi:
            return Signal.BUY
        if momentum > self.exit_rsi:
            return Signal.SELL
        return Signal.HOLD
