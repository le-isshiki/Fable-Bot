"""Exchange wrapper tests: candle pagination and testnet data routing.

No network: the ccxt clients are replaced with fakes after construction.
"""

from fable_bot.config import ExchangeConfig
from fable_bot.exchange import Exchange

HOUR_MS = 3_600_000


class FakeDataClient:
    """Mimics ccxt fetch_ohlcv semantics: returns up to `limit` candles from `since`."""

    def __init__(self, history_hours: int, start_ms: int = 1_700_000_000_000):
        self.candles = [
            [start_ms + i * HOUR_MS, 100.0, 101.0, 99.0, 100.5, 10.0]
            for i in range(history_hours)
        ]
        self.calls = 0

    def milliseconds(self) -> int:
        return self.candles[-1][0] + HOUR_MS

    def fetch_ohlcv(self, symbol, timeframe=None, since=None, limit=None):
        self.calls += 1
        data = self.candles
        if since is not None:
            data = [c for c in data if c[0] >= since]
        return data[:limit]


def make_exchange(history_hours: int) -> tuple[Exchange, FakeDataClient]:
    ex = Exchange(ExchangeConfig(testnet=True), dry_run=True)
    fake = FakeDataClient(history_hours)
    ex.data_client = fake
    return ex, fake


def test_small_request_is_a_single_call():
    ex, fake = make_exchange(history_hours=1500)
    candles = ex.fetch_candles("BTC/USDT", "1h", 500)
    assert len(candles) == 500
    assert fake.calls == 1


def test_pagination_past_the_per_request_cap():
    ex, fake = make_exchange(history_hours=3500)
    candles = ex.fetch_candles("BTC/USDT", "1h", 3000)
    assert len(candles) == 3000
    assert fake.calls >= 3
    timestamps = [c[0] for c in candles]
    assert timestamps == sorted(timestamps)
    assert len(set(timestamps)) == len(timestamps), "no duplicate candles"
    # The most recent candles, not the oldest.
    assert candles[-1][0] == fake.candles[-1][0]


def test_short_history_returns_what_exists_without_looping():
    ex, _ = make_exchange(history_hours=684)
    candles = ex.fetch_candles("BTC/USDT", "1h", 3000)
    assert len(candles) == 684


def test_testnet_uses_separate_production_data_client():
    ex = Exchange(ExchangeConfig(testnet=True), dry_run=True)
    assert ex.data_client is not ex.client


def test_mainnet_reuses_the_order_client_for_data():
    ex = Exchange(ExchangeConfig(testnet=False), dry_run=True)
    assert ex.data_client is ex.client
