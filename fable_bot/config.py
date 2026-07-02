"""Configuration loading: config.yaml for behavior, environment for secrets."""

import os
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv


@dataclass
class ExchangeConfig:
    testnet: bool = True
    api_key: str = ""
    api_secret: str = ""


@dataclass
class TradingConfig:
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    candle_history: int = 200
    state_file: str = "state.json"


@dataclass
class StrategyConfig:
    name: str = "sma_crossover"
    params: dict = field(default_factory=dict)


@dataclass
class RiskConfig:
    max_position_pct: float = 0.10
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    max_daily_loss_pct: float = 0.05
    min_order_quote: float = 10.0


@dataclass
class LoopConfig:
    poll_interval_seconds: int = 60


@dataclass
class Config:
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)


def load_config(path: str = "config.yaml") -> Config:
    load_dotenv()
    raw = {}
    if os.path.exists(path):
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

    cfg = Config(
        exchange=ExchangeConfig(**raw.get("exchange", {})),
        trading=TradingConfig(**raw.get("trading", {})),
        strategy=StrategyConfig(**raw.get("strategy", {})),
        risk=RiskConfig(**raw.get("risk", {})),
        loop=LoopConfig(**raw.get("loop", {})),
    )
    cfg.exchange.api_key = os.environ.get("BINANCE_API_KEY", "")
    cfg.exchange.api_secret = os.environ.get("BINANCE_API_SECRET", "")
    return cfg
