import math
import random

from fable_bot.config import RiskConfig
from fable_bot.data import load_csv, save_csv
from fable_bot.optimize import PARAM_GRIDS, format_report, optimize
from fable_bot.strategies import STRATEGIES, Signal
from fable_bot.strategies.macd_momentum import MacdMomentum


def synthetic_candles(n: int = 800, seed: int = 42, start: float = 100.0) -> list[list[float]]:
    """Geometric random walk with alternating trend regimes — crypto-like test data."""
    rng = random.Random(seed)
    candles = []
    price = start
    drift = 0.0005
    for i in range(n):
        if i % 150 == 0:
            drift = rng.choice([0.002, -0.002, 0.0])
        ret = drift + rng.gauss(0, 0.01)
        new_price = price * math.exp(ret)
        high = max(price, new_price) * (1 + abs(rng.gauss(0, 0.003)))
        low = min(price, new_price) * (1 - abs(rng.gauss(0, 0.003)))
        candles.append([float(i * 3_600_000), price, high, low, new_price, rng.uniform(10, 100)])
        price = new_price
    return candles


def test_grids_cover_all_registered_strategies():
    assert set(PARAM_GRIDS) == set(STRATEGIES)


def test_macd_emits_buy_and_sell_on_regime_change():
    closes = [100.0] * 60 + [100 + i for i in range(40)] + [140 - i for i in range(40)]
    candles = [[float(i), c, c, c, c, 1.0] for i, c in enumerate(closes)]
    strat = MacdMomentum()
    signals = {strat.signal(candles[: i + 1]) for i in range(len(candles))}
    assert Signal.BUY in signals
    assert Signal.SELL in signals


def test_optimize_ranks_by_out_of_sample_score():
    results = optimize(synthetic_candles(), RiskConfig(min_order_quote=1.0), top_n=5)
    assert results
    assert all(c.test is not None for c in results)
    scores = [c.score(c.test) for c in results]
    assert scores == sorted(scores, reverse=True)


def test_optimize_respects_strategy_subset():
    results = optimize(synthetic_candles(), RiskConfig(min_order_quote=1.0),
                       strategies=["sma_crossover"], top_n=5)
    assert results
    assert {c.strategy for c in results} == {"sma_crossover"}


def test_format_report_mentions_overfitting_warning():
    results = optimize(synthetic_candles(), RiskConfig(min_order_quote=1.0), top_n=3)
    report = format_report(results, 800, "1h")
    assert "OUT-OF-SAMPLE" in report
    assert "overfit" in report


def test_csv_roundtrip(tmp_path):
    candles = synthetic_candles(50)
    path = tmp_path / "candles.csv"
    save_csv(str(path), candles)
    loaded = load_csv(str(path))
    assert len(loaded) == 50
    assert loaded[0][4] == candles[0][4]


def test_csv_seconds_timestamps_upscaled(tmp_path):
    path = tmp_path / "candles.csv"
    path.write_text("ts,o,h,l,c,v\n1700000000,1,2,0.5,1.5,10\n")
    loaded = load_csv(str(path))
    assert loaded[0][0] == 1700000000 * 1000
