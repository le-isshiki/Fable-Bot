"""Two experiments that bound what any trading bot can earn.

Experiment 1: what does a PERFECT trader — one that knows every future bar —
earn per day on this data, before and after exchange fees? No real strategy
can beat its own oracle.

Experiment 2: search hard for the most spectacular backtest in each window
(the number scam bots advertise), then trade that exact config on the data
that comes immediately after, and watch what it actually earns.

Usage:
    python scripts/reality_check.py path/to/candles_1h.csv
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fable_bot.backtest import run_backtest
from fable_bot.config import RiskConfig
from fable_bot.data import load_csv
from fable_bot.strategies import build_strategy

if len(sys.argv) != 2:
    sys.exit(__doc__)
candles = load_csv(sys.argv[1])
closes = [c[4] for c in candles]
rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
n_days = len(rets) / 24

vol = (sum(r * r for r in rets) / len(rets)) ** 0.5
print(f"Data: {len(closes)} hourly candles (~{n_days:.0f} days), hourly volatility {vol:.2%}")
print(f"(real BTC/USDT hourly volatility is typically 0.4%-1.0%, so this is comparable)\n")

print("=== EXPERIMENT 1: the omniscient oracle ===")
FEE = 0.001  # 0.1% per side, Binance standard
wealth_nofee, wealth_fee = 1.0, 1.0
for r in rets:
    if r > 0:
        wealth_nofee *= 1 + r
        traded = (1 + r) * (1 - FEE) ** 2
        if traded > 1:  # oracle skips bars where fees exceed the gain
            wealth_fee *= traded

daily_nofee = wealth_nofee ** (1 / n_days) - 1
daily_fee = wealth_fee ** (1 / n_days) - 1
print(f"Perfect foresight, zero fees:   {daily_nofee:+.2%} per day")
print(f"Perfect foresight, 0.1% fees:   {daily_fee:+.2%} per day")
print(f"Target claimed achievable:      +30.00% per day")
print(f"=> even literal omniscience on hourly bars earns "
      f"{'LESS THAN' if daily_fee < 0.30 else 'more than'} the target "
      f"({daily_fee / 0.30:.1%} of it, after fees)\n")

print("=== EXPERIMENT 2: manufacturing a spectacular backtest ===")
risk = RiskConfig(max_position_pct=1.0, stop_loss_pct=0.05, take_profit_pct=0.10,
                  max_daily_loss_pct=1.0, min_order_quote=1.0)

grids = {
    "sma_crossover": [{"fast_period": f, "slow_period": s}
                      for f in range(2, 16) for s in range(17, 80, 3) if f < s],
    "rsi_reversion": [{"period": p, "oversold": float(lo), "overbought": float(hi)}
                      for p in range(3, 22, 2) for lo in range(15, 45, 5) for hi in range(55, 90, 5)],
    "macd_momentum": [{"fast_period": f, "slow_period": s, "signal_period": g}
                      for f in range(3, 14, 2) for s in range(15, 45, 4) for g in (3, 5, 9) if f < s],
}

WINDOW = 400  # ~17 days
results = []
for start in range(0, len(candles) - 2 * WINDOW, WINDOW):
    train = candles[start: start + WINDOW]
    test = candles[start + WINDOW: start + 2 * WINDOW]
    best = None
    for name, combos in grids.items():
        for params in combos:
            strat = build_strategy(name, params)
            if len(train) <= strat.min_candles + 20:
                continue
            r = run_backtest(strat, train, risk, fee_pct=FEE)
            if r.trades and (best is None or r.return_pct > best[2].return_pct):
                best = (name, params, r)
    if best is None:
        continue
    name, params, train_res = best
    test_res = run_backtest(build_strategy(name, params), test, risk, fee_pct=FEE)
    results.append((start, name, params, train_res, test_res))

print(f"Searched {sum(len(v) for v in grids.values())} configs per window, "
      f"100% of balance per trade, picked each window's best backtest:\n")
print(f"{'window':<8} {'best strategy':<35} {'backtest ret':>12} {'NEXT 17 days':>13}")
for start, name, params, tr, te in results:
    p = ",".join(f"{k.split('_')[0]}={v:g}" for k, v in params.items())
    print(f"{start:<8} {name + '(' + p + ')':<35} {tr.return_pct:>11.1%} {te.return_pct:>12.1%}")

avg_train = sum(r[3].return_pct for r in results) / len(results)
avg_test = sum(r[4].return_pct for r in results) / len(results)
wealth = 1.0
for r in results:
    wealth *= 1 + r[4].return_pct
print(f"\nAverage 'spectacular backtest' return: {avg_train:+.1%} per window")
print(f"Average return when actually traded forward: {avg_test:+.1%} per window")
print(f"Compounded result of always trading last window's best config: {wealth - 1:+.1%}")
