"""Position sizing and protective exits, independent of any strategy."""

import logging
from dataclasses import dataclass
from datetime import date

from fable_bot.config import RiskConfig

log = logging.getLogger(__name__)


@dataclass
class Position:
    entry_price: float
    amount: float  # base currency


class RiskManager:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg
        self._day: date | None = None
        self._day_start_equity = 0.0
        self._day_realized_pnl = 0.0

    def position_size(self, quote_balance: float) -> float:
        """Quote currency to commit to a new position; 0 if below exchange minimum."""
        size = quote_balance * self.cfg.max_position_pct
        return size if size >= self.cfg.min_order_quote else 0.0

    def should_exit(self, position: Position, price: float) -> str | None:
        """Return the exit reason if a protective exit has triggered, else None."""
        change = (price - position.entry_price) / position.entry_price
        if change <= -self.cfg.stop_loss_pct:
            return f"stop-loss ({change:+.2%})"
        if change >= self.cfg.take_profit_pct:
            return f"take-profit ({change:+.2%})"
        return None

    def record_trade(self, pnl: float, today: date | None = None) -> None:
        self._roll_day(today or date.today())
        self._day_realized_pnl += pnl

    def can_open(self, equity: float, today: date | None = None) -> bool:
        """False once today's realized losses exceed the daily cap."""
        self._roll_day(today or date.today(), equity)
        if self._day_start_equity <= 0:
            return True
        drawdown = -self._day_realized_pnl / self._day_start_equity
        if drawdown >= self.cfg.max_daily_loss_pct:
            log.warning("Daily loss cap hit (%.2f%% lost) — no new positions today", drawdown * 100)
            return False
        return True

    def _roll_day(self, today: date, equity: float | None = None) -> None:
        if self._day != today:
            self._day = today
            self._day_realized_pnl = 0.0
            self._day_start_equity = equity if equity is not None else self._day_start_equity
        elif self._day_start_equity == 0.0 and equity is not None:
            self._day_start_equity = equity
