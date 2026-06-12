from fable_bot.strategies.base import Signal, Strategy
from fable_bot.strategies.rsi_reversion import RsiReversion
from fable_bot.strategies.sma_crossover import SmaCrossover

STRATEGIES: dict[str, type[Strategy]] = {
    "sma_crossover": SmaCrossover,
    "rsi_reversion": RsiReversion,
}


def build_strategy(name: str, params: dict) -> Strategy:
    if name not in STRATEGIES:
        raise ValueError(f"Unknown strategy '{name}'. Available: {', '.join(sorted(STRATEGIES))}")
    return STRATEGIES[name](**params)
