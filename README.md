# Fable-Bot

An automated spot-trading bot for Binance, built around three safety layers:

1. **Dry-run by default** — `python main.py run` paper-trades against live prices; no order ever leaves the process unless you pass `--live`.
2. **Testnet by default** — even with `--live`, orders go to the [Binance spot testnet](https://testnet.binance.vision/) until you set `exchange.testnet: false` in `config.yaml` **and** export `FABLE_BOT_CONFIRM_LIVE=yes`. Market data always comes from the production public API (the testnet's candle history is tiny and its order book is a toy); only orders are routed to the testnet.
3. **Risk manager** — stop-loss, take-profit, per-trade position sizing, and a daily loss cap are enforced outside the strategy, so a misbehaving strategy can't bypass them.

## Setup

Requires **Python 3.10+** (`ccxt` no longer installs on 3.9). macOS ships an older
Python with the Xcode command-line tools, so check `python3 --version` first and, if
it reports 3.9 or older, install a current one with `brew install python` or from
[python.org/downloads](https://www.python.org/downloads/) (then open a new terminal).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your API keys (not needed for backtesting/dry-run)
```

## Usage

```bash
# Backtest the configured strategy on the last 1000 candles
python main.py backtest --limit 1000

# Search all strategies/parameters for the best historical config,
# validated on unseen out-of-sample data (this is the "study the market" command)
python main.py optimize --limit 3000

# Both commands also accept --csv to run on exported candle data
python main.py backtest --csv btcusdt_1h.csv

# Paper trade live prices (no API keys required, no orders placed)
python main.py run

# Trade on the Binance spot testnet (requires testnet API keys in .env)
python main.py run --live

# Trade real funds: set exchange.testnet: false in config.yaml, then
FABLE_BOT_CONFIRM_LIVE=yes python main.py run --live
```

## Configuration

Everything lives in `config.yaml`:

| Section | What it controls |
|---|---|
| `exchange.testnet` | Testnet vs. real Binance for `--live` orders |
| `trading` | Symbol, candle timeframe, history depth |
| `strategy` | Strategy name + parameters |
| `risk` | Position size %, stop-loss %, take-profit %, daily loss cap, min order size |
| `loop` | Polling interval |

API keys are read from the environment (`.env` is supported), never from `config.yaml`.

## Strategies

- **`sma_crossover`** (default) — trend-following; buys when the fast SMA crosses above the slow SMA, sells on the reverse cross. Params: `fast_period`, `slow_period`.
- **`rsi_reversion`** — mean reversion; buys when RSI drops below `oversold`, sells above `overbought`. Params: `period`, `oversold`, `overbought`.
- **`macd_momentum`** — momentum; buys when the MACD line crosses above its signal line, sells on the cross below. Params: `fast_period`, `slow_period`, `signal_period`.

To add your own, subclass `Strategy` in `fable_bot/strategies/` and register it in `fable_bot/strategies/__init__.py`. Strategies only emit BUY/SELL/HOLD signals; entries, exits, and sizing stay with the trader and risk manager.

## Finding a good configuration

`python main.py optimize` grid-searches every registered strategy's parameters with **walk-forward validation**: configurations are tuned on the first 70% of the history and ranked by how they perform on the unseen final 30%. This guards against the classic trap of picking a config that merely memorized the past. Rank by the `test ret` column; a config whose `train ret` is great but whose `test ret` is poor is overfit and should not be trusted.

Realistic expectations: a sound spot strategy earns **single-digit percent per month** with losing stretches, not fixed daily profits. Any tool or person promising guaranteed daily returns (e.g. "30% a day") is describing something mathematically impossible to sustain — treat it as a scam signal.

## Tests

```bash
pytest
```

## Disclaimer

Trading cryptocurrency is risky and this software is provided as-is, with no warranty of profitability or correctness. Backtest results do not guarantee future performance. Start on the testnet, use money you can afford to lose, and review every line before going live.
