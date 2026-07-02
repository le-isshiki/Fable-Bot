"""Previous-day-range volatility breakout — the classic day-trader system
popularized by Larry Williams and Toby Crabel, still widely used on real
desks and documented for crypto specifically.

The idea: most days are noise; a day only becomes worth trading when price
decisively escapes yesterday's range. Buy when price clears today's UTC
open plus range_mult x yesterday's (high - low); flatten before the day
rolls over. At most one entry per day by construction — a day-trader's
rhythm, not a scalper's. An optional slow-SMA filter keeps entries on the
right side of the larger trend.

Intraday risk (stop-loss / take-profit) stays with the RiskManager, as for
every strategy.
"""

from fable_bot.strategies.base import Signal, Strategy, closes, sma

DAY_MS = 86_400_000


class DayBreakout(Strategy):
    def __init__(self, range_mult: float = 0.5, trend_period: int = 0):
        if range_mult <= 0:
            raise ValueError("range_mult must be positive")
        if trend_period < 0:
            raise ValueError("trend_period must be >= 0")
        self.range_mult = range_mult
        self.trend_period = trend_period

    @property
    def min_candles(self) -> int:
        # A full previous day of hourly candles plus today's first candle;
        # the completeness check in signal() guards finer timeframes.
        return max(25, self.trend_period + 1)

    def signal(self, candles: list[list[float]]) -> Signal:
        if len(candles) < self.min_candles:
            return Signal.HOLD
        last_ts = candles[-1][0]
        tf_ms = last_ts - candles[-2][0]
        if tf_ms <= 0:
            return Signal.HOLD

        today_start = (last_ts // DAY_MS) * DAY_MS
        prev = [c for c in candles if today_start - DAY_MS <= c[0] < today_start]
        today = [c for c in candles if c[0] >= today_start]
        # Yesterday's range is only meaningful if we saw (nearly) all of yesterday.
        if not today or len(prev) < 0.8 * (DAY_MS // tf_ms):
            return Signal.HOLD

        # Final candle of the day: flatten — this strategy holds intraday only.
        if last_ts + 2 * tf_ms > today_start + DAY_MS:
            return Signal.SELL

        prev_range = max(c[2] for c in prev) - min(c[3] for c in prev)
        trigger = today[0][1] + self.range_mult * prev_range

        prices = closes(candles)
        if self.trend_period and prices[-1] < sma(prices, self.trend_period):
            return Signal.HOLD
        if prices[-1] > trigger:
            return Signal.BUY
        return Signal.HOLD
