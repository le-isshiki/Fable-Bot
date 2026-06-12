"""Bar-by-bar backtester applying the same risk rules as live trading."""

import logging
from dataclasses import dataclass, field

from fable_bot.config import RiskConfig
from fable_bot.risk import Position
from fable_bot.strategies import Signal, Strategy

log = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    trades: int = 0
    wins: int = 0
    pnl: float = 0.0
    starting_balance: float = 0.0
    ending_balance: float = 0.0
    max_drawdown_pct: float = 0.0
    trade_log: list[dict] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return self.wins / self.trades if self.trades else 0.0

    @property
    def return_pct(self) -> float:
        if not self.starting_balance:
            return 0.0
        return (self.ending_balance - self.starting_balance) / self.starting_balance

    def summary(self) -> str:
        return (
            f"Trades: {self.trades}  Win rate: {self.win_rate:.1%}\n"
            f"PnL: {self.pnl:+.2f}  Return: {self.return_pct:+.2%}\n"
            f"Max drawdown: {self.max_drawdown_pct:.2%}\n"
            f"Balance: {self.starting_balance:.2f} -> {self.ending_balance:.2f}"
        )


def run_backtest(
    strategy: Strategy,
    candles: list[list[float]],
    risk: RiskConfig,
    starting_balance: float = 1000.0,
    fee_pct: float = 0.001,
) -> BacktestResult:
    """Replay candles oldest-to-newest. Fills happen at the close of the signal bar;
    stop-loss/take-profit are checked against each bar's high/low.
    """
    result = BacktestResult(starting_balance=starting_balance, ending_balance=starting_balance)
    quote = starting_balance
    position: Position | None = None
    peak_equity = starting_balance

    def close_position(price: float, reason: str, ts: float) -> None:
        nonlocal quote, position
        assert position is not None
        proceeds = position.amount * price * (1 - fee_pct)
        pnl = proceeds - position.amount * position.entry_price
        quote += proceeds
        result.trades += 1
        result.wins += pnl > 0
        result.pnl += pnl
        result.trade_log.append({
            "timestamp": ts, "entry": position.entry_price, "exit": price,
            "pnl": pnl, "reason": reason,
        })
        position = None

    for i in range(strategy.min_candles, len(candles)):
        window = candles[: i + 1]
        ts, _o, high, low, close, _v = candles[i]

        if position:
            stop = position.entry_price * (1 - risk.stop_loss_pct)
            target = position.entry_price * (1 + risk.take_profit_pct)
            if low <= stop:
                close_position(stop, "stop-loss", ts)
            elif high >= target:
                close_position(target, "take-profit", ts)

        signal = strategy.signal(window)
        if signal is Signal.BUY and position is None:
            quote_amount = quote * risk.max_position_pct
            if quote_amount >= risk.min_order_quote:
                amount = quote_amount * (1 - fee_pct) / close
                quote -= quote_amount
                position = Position(entry_price=close, amount=amount)
        elif signal is Signal.SELL and position is not None:
            close_position(close, "signal", ts)

        equity = quote + (position.amount * close if position else 0.0)
        peak_equity = max(peak_equity, equity)
        drawdown = (peak_equity - equity) / peak_equity
        result.max_drawdown_pct = max(result.max_drawdown_pct, drawdown)

    final_close = candles[-1][4]
    if position:
        close_position(final_close, "end-of-data", candles[-1][0])
    result.ending_balance = quote
    return result
