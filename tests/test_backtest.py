from fable_bot.backtest import run_backtest
from fable_bot.config import RiskConfig
from fable_bot.strategies import Signal, Strategy


def make_candles(closes: list[float]) -> list[list[float]]:
    return [[float(i), c, c * 1.001, c * 0.999, c, 1.0] for i, c in enumerate(closes)]


class BuyOnce(Strategy):
    """Buys on the first candle it sees, then holds forever."""

    def __init__(self):
        self.bought = False

    @property
    def min_candles(self) -> int:
        return 1

    def signal(self, candles):
        if not self.bought:
            self.bought = True
            return Signal.BUY
        return Signal.HOLD


def test_take_profit_exit():
    closes = [100.0] * 5 + [101, 102, 103, 104, 105, 106]
    risk = RiskConfig(max_position_pct=0.5, stop_loss_pct=0.02, take_profit_pct=0.04, min_order_quote=1.0)
    result = run_backtest(BuyOnce(), make_candles(closes), risk, starting_balance=1000.0, fee_pct=0.0)
    assert result.trades == 1
    assert result.trade_log[0]["reason"] == "take-profit"
    assert result.pnl > 0


def test_stop_loss_exit():
    closes = [100.0] * 5 + [99, 98, 97, 96, 95]
    risk = RiskConfig(max_position_pct=0.5, stop_loss_pct=0.02, take_profit_pct=0.10, min_order_quote=1.0)
    result = run_backtest(BuyOnce(), make_candles(closes), risk, starting_balance=1000.0, fee_pct=0.0)
    assert result.trades == 1
    assert result.trade_log[0]["reason"] == "stop-loss"
    assert result.pnl < 0
    # Loss is bounded by stop-loss percent of the committed amount (plus slippage to the stop price).
    assert result.pnl >= -1000.0 * 0.5 * 0.025


def test_open_position_closed_at_end_of_data():
    closes = [100.0] * 10
    risk = RiskConfig(max_position_pct=0.5, min_order_quote=1.0)
    result = run_backtest(BuyOnce(), make_candles(closes), risk, starting_balance=1000.0, fee_pct=0.0)
    assert result.trades == 1
    assert result.trade_log[0]["reason"] == "end-of-data"
    assert abs(result.ending_balance - 1000.0) < 1e-6


def test_fees_reduce_pnl():
    closes = [100.0] * 5 + [101, 102, 103, 104, 105]
    risk = RiskConfig(max_position_pct=0.5, take_profit_pct=0.04, min_order_quote=1.0)
    no_fee = run_backtest(BuyOnce(), make_candles(closes), risk, fee_pct=0.0)
    with_fee = run_backtest(BuyOnce(), make_candles(closes), risk, fee_pct=0.001)
    assert with_fee.pnl < no_fee.pnl


def test_no_trade_below_min_order_size():
    closes = [100.0] * 10
    risk = RiskConfig(max_position_pct=0.01, min_order_quote=50.0)  # 1% of 1000 = 10 < 50
    result = run_backtest(BuyOnce(), make_candles(closes), risk, starting_balance=1000.0)
    assert result.trades == 0
