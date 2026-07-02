"""Thin wrapper around ccxt's Binance client with dry-run order simulation.

In dry-run mode market data is real but orders never leave the process:
fills are simulated at the latest price against a paper balance.

Market data (candles, tickers) always comes from the production public API,
even in testnet mode: the testnet's order book is a toy and its candle
history is tiny and resets, so backtests and signals run on it are garbage.
Only orders are routed to the testnet.
"""

import logging

import ccxt

from fable_bot.config import ExchangeConfig

log = logging.getLogger(__name__)

# Binance returns at most this many candles per OHLCV request.
_MAX_CANDLE_BATCH = 1000


class Exchange:
    def __init__(self, cfg: ExchangeConfig, dry_run: bool = True, paper_quote_balance: float = 1000.0):
        self.dry_run = dry_run
        self.client = ccxt.binance({
            "apiKey": cfg.api_key,
            "secret": cfg.api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        if cfg.testnet:
            self.client.set_sandbox_mode(True)
            # Public market data needs no keys; keep it on production.
            self.data_client = ccxt.binance({
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            })
        else:
            self.data_client = self.client

        # Paper balances used only in dry-run mode, keyed by currency code.
        self._paper: dict[str, float] = {"QUOTE": paper_quote_balance, "BASE": 0.0}

    def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> list[list[float]]:
        """Fetch the `limit` most recent candles, paginating past the per-request cap."""
        if limit <= _MAX_CANDLE_BATCH:
            return self.data_client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

        tf_ms = ccxt.Exchange.parse_timeframe(timeframe) * 1000
        since = self.data_client.milliseconds() - limit * tf_ms
        candles: list[list[float]] = []
        while len(candles) < limit:
            batch = self.data_client.fetch_ohlcv(
                symbol, timeframe=timeframe, since=since, limit=_MAX_CANDLE_BATCH
            )
            fresh = [c for c in batch if not candles or c[0] > candles[-1][0]]
            if not fresh:
                break
            candles.extend(fresh)
            since = candles[-1][0] + 1
        if len(candles) < limit:
            log.warning("Requested %d candles but the exchange only had %d", limit, len(candles))
        return candles[-limit:]

    def last_price(self, symbol: str) -> float:
        return float(self.data_client.fetch_ticker(symbol)["last"])

    def paper_balances(self) -> dict[str, float]:
        return dict(self._paper)

    def set_paper_balances(self, balances: dict[str, float]) -> None:
        self._paper.update({k: float(v) for k, v in balances.items()})

    def balances(self, symbol: str) -> tuple[float, float]:
        """Return (base_free, quote_free) for the given symbol, e.g. (BTC, USDT)."""
        if self.dry_run:
            return self._paper["BASE"], self._paper["QUOTE"]
        base, quote = symbol.split("/")
        bal = self.client.fetch_balance()
        return float(bal.get(base, {}).get("free", 0.0)), float(bal.get(quote, {}).get("free", 0.0))

    def market_buy(self, symbol: str, quote_amount: float) -> dict:
        """Spend quote_amount of quote currency buying the base asset."""
        price = self.last_price(symbol)
        amount = quote_amount / price
        if self.dry_run:
            self._paper["QUOTE"] -= quote_amount
            self._paper["BASE"] += amount
            log.info("[DRY-RUN] BUY %s %.8f @ %.2f (%.2f quote)", symbol, amount, price, quote_amount)
            return {"price": price, "amount": amount, "cost": quote_amount, "simulated": True}
        order = self.client.create_market_buy_order(symbol, self.client.amount_to_precision(symbol, amount))
        log.info("BUY %s id=%s", symbol, order.get("id"))
        return order

    def market_sell(self, symbol: str, base_amount: float) -> dict:
        price = self.last_price(symbol)
        if self.dry_run:
            self._paper["BASE"] -= base_amount
            self._paper["QUOTE"] += base_amount * price
            log.info("[DRY-RUN] SELL %s %.8f @ %.2f", symbol, base_amount, price)
            return {"price": price, "amount": base_amount, "cost": base_amount * price, "simulated": True}
        order = self.client.create_market_sell_order(symbol, self.client.amount_to_precision(symbol, base_amount))
        log.info("SELL %s id=%s", symbol, order.get("id"))
        return order
