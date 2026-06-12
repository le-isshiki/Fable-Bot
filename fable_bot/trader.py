"""Main trading loop: long-only spot trading driven by strategy signals,
with stop-loss / take-profit / daily-loss-cap enforcement from RiskManager.
"""

import logging
import time

from fable_bot.config import Config
from fable_bot.exchange import Exchange
from fable_bot.risk import Position, RiskManager
from fable_bot.strategies import Signal, Strategy, build_strategy

log = logging.getLogger(__name__)


class Trader:
    def __init__(self, cfg: Config, exchange: Exchange, strategy: Strategy | None = None):
        self.cfg = cfg
        self.exchange = exchange
        self.strategy = strategy or build_strategy(cfg.strategy.name, cfg.strategy.params)
        self.risk = RiskManager(cfg.risk)
        self.position: Position | None = None

        if cfg.trading.candle_history < self.strategy.min_candles:
            raise ValueError(
                f"trading.candle_history={cfg.trading.candle_history} is below the "
                f"strategy minimum of {self.strategy.min_candles}"
            )

    def run_forever(self) -> None:
        symbol = self.cfg.trading.symbol
        mode = "DRY-RUN" if self.exchange.dry_run else "LIVE"
        log.info("Starting trader [%s] %s %s strategy=%s",
                 mode, symbol, self.cfg.trading.timeframe, self.cfg.strategy.name)
        while True:
            try:
                self.step()
            except KeyboardInterrupt:
                log.info("Interrupted — shutting down")
                return
            except Exception:
                log.exception("Cycle failed; retrying next interval")
            time.sleep(self.cfg.loop.poll_interval_seconds)

    def step(self) -> None:
        symbol = self.cfg.trading.symbol
        candles = self.exchange.fetch_candles(
            symbol, self.cfg.trading.timeframe, self.cfg.trading.candle_history
        )
        price = candles[-1][4]

        # Protective exits take priority over strategy signals.
        if self.position:
            reason = self.risk.should_exit(self.position, price)
            if reason:
                log.info("Exiting position: %s", reason)
                self._close(price)
                return

        signal = self.strategy.signal(candles)
        if signal is Signal.BUY and self.position is None:
            self._open(price)
        elif signal is Signal.SELL and self.position is not None:
            log.info("Strategy sell signal")
            self._close(price)

    def _open(self, price: float) -> None:
        symbol = self.cfg.trading.symbol
        base, quote = self.exchange.balances(symbol)
        equity = quote + base * price
        if not self.risk.can_open(equity):
            return
        quote_amount = self.risk.position_size(quote)
        if quote_amount <= 0:
            log.info("Buy signal skipped: position size below minimum (quote balance %.2f)", quote)
            return
        order = self.exchange.market_buy(symbol, quote_amount)
        self.position = Position(entry_price=float(order["price"] or price),
                                 amount=float(order["amount"]))
        log.info("Opened position: %.8f @ %.2f", self.position.amount, self.position.entry_price)

    def _close(self, price: float) -> None:
        assert self.position is not None
        order = self.exchange.market_sell(self.cfg.trading.symbol, self.position.amount)
        fill = float(order["price"] or price)
        pnl = (fill - self.position.entry_price) * self.position.amount
        self.risk.record_trade(pnl)
        log.info("Closed position: %.8f @ %.2f pnl=%+.2f", self.position.amount, fill, pnl)
        self.position = None
