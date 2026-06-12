"""Strategy interface. Candles are ccxt-style OHLCV rows:
[timestamp_ms, open, high, low, close, volume], oldest first.
"""

from abc import ABC, abstractmethod
from enum import Enum


class Signal(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class Strategy(ABC):
    @property
    @abstractmethod
    def min_candles(self) -> int:
        """Minimum candle history required to produce a signal."""

    @abstractmethod
    def signal(self, candles: list[list[float]]) -> Signal:
        """Return the trading signal for the most recent candle."""


def closes(candles: list[list[float]]) -> list[float]:
    return [c[4] for c in candles]


def sma(values: list[float], period: int) -> float:
    return sum(values[-period:]) / period
