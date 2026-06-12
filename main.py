"""Fable-Bot CLI.

  python main.py backtest              # backtest the configured strategy on recent history
  python main.py run                   # paper trade live prices (no orders placed)
  python main.py run --live            # place real orders (testnet unless disabled in config)
"""

import argparse
import logging
import os
import sys

from fable_bot.backtest import run_backtest
from fable_bot.config import load_config
from fable_bot.data import load_csv
from fable_bot.exchange import Exchange
from fable_bot.optimize import format_report, optimize
from fable_bot.strategies import build_strategy
from fable_bot.trader import Trader


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    dry_run = not args.live

    if args.live:
        if not cfg.exchange.api_key or not cfg.exchange.api_secret:
            print("error: --live requires BINANCE_API_KEY and BINANCE_API_SECRET in the environment")
            return 1
        if not cfg.exchange.testnet and os.environ.get("FABLE_BOT_CONFIRM_LIVE") != "yes":
            print(
                "error: refusing to trade real funds. config.yaml has exchange.testnet: false;\n"
                "set FABLE_BOT_CONFIRM_LIVE=yes in the environment to confirm you intend this."
            )
            return 1

    exchange = Exchange(cfg.exchange, dry_run=dry_run, paper_quote_balance=args.paper_balance)
    Trader(cfg, exchange).run_forever()
    return 0


def _load_candles(args: argparse.Namespace, cfg) -> list[list[float]]:
    if args.csv:
        print(f"Loading candles from {args.csv}...")
        return load_csv(args.csv)
    exchange = Exchange(cfg.exchange, dry_run=True)
    print(f"Fetching {args.limit} {cfg.trading.timeframe} candles for {cfg.trading.symbol}...")
    return exchange.fetch_candles(cfg.trading.symbol, cfg.trading.timeframe, args.limit)


def cmd_backtest(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    strategy = build_strategy(cfg.strategy.name, cfg.strategy.params)
    candles = _load_candles(args, cfg)
    if len(candles) <= strategy.min_candles:
        print(f"error: only {len(candles)} candles available; strategy needs more than {strategy.min_candles}")
        return 1

    result = run_backtest(strategy, candles, cfg.risk, starting_balance=args.paper_balance)
    print(f"\n=== Backtest: {cfg.strategy.name} on {cfg.trading.symbol} {cfg.trading.timeframe} ===")
    print(result.summary())
    return 0


def cmd_optimize(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    candles = _load_candles(args, cfg)
    strategies = args.strategies.split(",") if args.strategies else None
    print(f"Searching parameter grids ({len(candles)} candles, "
          f"{args.train_fraction:.0%} train / {1 - args.train_fraction:.0%} test)...\n")
    results = optimize(candles, cfg.risk, strategies=strategies,
                       train_fraction=args.train_fraction, top_n=args.top)
    print(format_report(results, len(candles), cfg.trading.timeframe))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="fable-bot", description="Binance trading bot")
    parser.add_argument("--config", default="config.yaml", help="path to config file")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run the trading loop")
    p_run.add_argument("--live", action="store_true",
                       help="place real orders (default is dry-run paper trading)")
    p_run.add_argument("--paper-balance", type=float, default=1000.0,
                       help="starting quote balance for dry-run mode")
    p_run.set_defaults(func=cmd_run)

    p_bt = sub.add_parser("backtest", help="backtest the configured strategy")
    p_bt.add_argument("--limit", type=int, default=1000, help="number of historical candles")
    p_bt.add_argument("--csv", help="load candles from a CSV file instead of the exchange")
    p_bt.add_argument("--paper-balance", type=float, default=1000.0)
    p_bt.set_defaults(func=cmd_backtest)

    p_opt = sub.add_parser(
        "optimize",
        help="grid-search strategy parameters with walk-forward validation",
    )
    p_opt.add_argument("--limit", type=int, default=1000, help="number of historical candles")
    p_opt.add_argument("--csv", help="load candles from a CSV file instead of the exchange")
    p_opt.add_argument("--strategies", help="comma-separated subset, e.g. sma_crossover,macd_momentum")
    p_opt.add_argument("--train-fraction", type=float, default=0.7,
                       help="fraction of history used for training (rest is out-of-sample)")
    p_opt.add_argument("--top", type=int, default=10, help="number of configurations to report")
    p_opt.set_defaults(func=cmd_optimize)

    args = parser.parse_args()
    setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
