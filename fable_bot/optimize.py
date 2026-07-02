"""Grid-search strategy parameters with walk-forward (out-of-sample) validation.

The candle history is split into a training segment and a test segment.
Every parameter combination is backtested on the training segment; the
top candidates are then re-run on the unseen test segment, and ranking is
by test-segment performance. A configuration that only shines in-sample
is overfit and gets exposed here — this is the difference between
"studying the market" and fooling yourself.
"""

import itertools
from dataclasses import dataclass

from fable_bot.backtest import BacktestResult, run_backtest
from fable_bot.config import RiskConfig
from fable_bot.strategies import build_strategy

# Parameter grids per strategy. Values are deliberately coarse: fine-grained
# grids mostly find noise, not signal.
PARAM_GRIDS: dict[str, dict[str, list]] = {
    "sma_crossover": {
        "fast_period": [5, 9, 12, 20],
        "slow_period": [21, 30, 50, 100],
    },
    "rsi_reversion": {
        "period": [7, 14, 21],
        "oversold": [20.0, 25.0, 30.0],
        "overbought": [70.0, 75.0, 80.0],
    },
    "macd_momentum": {
        "fast_period": [8, 12],
        "slow_period": [21, 26, 35],
        "signal_period": [9],
    },
    "trend_pullback": {
        "trend_period": [50, 100, 200],
        "rsi_period": [7, 14],
        "entry_rsi": [35.0, 40.0, 45.0],
        "exit_rsi": [60.0, 70.0],
    },
}


@dataclass
class Candidate:
    strategy: str
    params: dict
    train: BacktestResult
    test: BacktestResult | None = None

    def score(self, result: BacktestResult) -> float:
        """Return penalized by drawdown — high return with deep drawdowns ranks low."""
        return result.return_pct - result.max_drawdown_pct


def _param_combos(grid: dict[str, list]) -> list[dict]:
    keys = list(grid)
    return [dict(zip(keys, combo)) for combo in itertools.product(*(grid[k] for k in keys))]


def optimize(
    candles: list[list[float]],
    risk: RiskConfig,
    strategies: list[str] | None = None,
    train_fraction: float = 0.7,
    top_n: int = 10,
    starting_balance: float = 1000.0,
    fee_pct: float = 0.001,
) -> list[Candidate]:
    """Return the top_n candidates ranked by out-of-sample (test segment) score."""
    split = int(len(candles) * train_fraction)
    train_candles, test_candles = candles[:split], candles[split:]

    candidates: list[Candidate] = []
    for name in strategies or sorted(PARAM_GRIDS):
        for params in _param_combos(PARAM_GRIDS[name]):
            try:
                strategy = build_strategy(name, params)
            except ValueError:
                continue  # invalid combo, e.g. fast >= slow
            if len(train_candles) <= strategy.min_candles * 2:
                continue
            result = run_backtest(strategy, train_candles, risk,
                                  starting_balance=starting_balance, fee_pct=fee_pct)
            if result.trades == 0:
                continue
            candidates.append(Candidate(strategy=name, params=params, train=result))

    # Validate the most promising training configs on unseen data.
    candidates.sort(key=lambda c: c.score(c.train), reverse=True)
    finalists = candidates[: top_n * 3]
    for cand in finalists:
        strategy = build_strategy(cand.strategy, cand.params)
        cand.test = run_backtest(strategy, test_candles, risk,
                                 starting_balance=starting_balance, fee_pct=fee_pct)

    # A config that never trades out-of-sample proves nothing — don't let its
    # flat 0%/0% outrank configs with real test evidence.
    traded = [c for c in finalists if c.test.trades > 0]
    finalists = traded or finalists
    finalists.sort(key=lambda c: c.score(c.test), reverse=True)
    return finalists[:top_n]


def format_report(results: list[Candidate], total_candles: int, timeframe: str) -> str:
    if not results:
        return "No strategy configuration produced any trades on this data."
    lines = [
        f"Walk-forward optimization over {total_candles} {timeframe} candles "
        f"(ranked by OUT-OF-SAMPLE return minus max drawdown)\n",
        f"{'#':>2}  {'strategy':<15} {'params':<42} {'train ret':>9} {'test ret':>9} "
        f"{'test dd':>8} {'trades':>6} {'win%':>5}",
    ]
    for i, c in enumerate(results, 1):
        params = ", ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
                           for k, v in c.params.items())
        lines.append(
            f"{i:>2}  {c.strategy:<15} {params:<42} {c.train.return_pct:>8.2%} "
            f"{c.test.return_pct:>8.2%} {c.test.max_drawdown_pct:>7.2%} "
            f"{c.test.trades:>6} {c.test.win_rate:>5.0%}"
        )
    lines.append(
        "\nRead 'test ret' (unseen data), not 'train ret'. A big gap between the two "
        "means the config is overfit. Past performance does not guarantee future results."
    )
    return "\n".join(lines)
