"""Generate synthetic OHLCV data for offline pipeline testing.

This is NOT market data — results on it say nothing about real profitability.
It exists so the backtest/optimize pipeline can be exercised where exchange
APIs are unreachable. For real research, export candles from Binance:

    python - <<'EOF'
    import ccxt, csv
    ex = ccxt.binance()
    rows = []
    since = None
    while len(rows) < 8000:
        batch = ex.fetch_ohlcv("BTC/USDT", "1h", since=since, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        since = batch[-1][0] + 1
    with open("btcusdt_1h.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        w.writerows(rows)
    EOF
"""

import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fable_bot.data import save_csv


def generate(n: int, seed: int, start_price: float) -> list[list[float]]:
    rng = random.Random(seed)
    candles = []
    price = start_price
    drift = 0.0
    for i in range(n):
        if i % 200 == 0:  # switch market regime every ~200 bars
            drift = rng.choice([0.0015, -0.0015, 0.0, 0.0005, -0.0005])
        ret = drift + rng.gauss(0, 0.012)
        new_price = price * math.exp(ret)
        high = max(price, new_price) * (1 + abs(rng.gauss(0, 0.004)))
        low = min(price, new_price) * (1 - abs(rng.gauss(0, 0.004)))
        candles.append([float(i * 3_600_000), price, high, low, new_price, rng.uniform(50, 500)])
        price = new_price
    return candles


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="synthetic_1h.csv")
    parser.add_argument("--candles", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--start-price", type=float, default=60000.0)
    args = parser.parse_args()
    save_csv(args.out, generate(args.candles, args.seed, args.start_price))
    print(f"Wrote {args.candles} synthetic candles to {args.out}")
