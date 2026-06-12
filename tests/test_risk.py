from datetime import date

from fable_bot.config import RiskConfig
from fable_bot.risk import Position, RiskManager


def test_position_size_respects_pct_and_minimum():
    rm = RiskManager(RiskConfig(max_position_pct=0.1, min_order_quote=10.0))
    assert rm.position_size(1000.0) == 100.0
    assert rm.position_size(50.0) == 0.0  # 10% of 50 = 5 < min_order_quote


def test_stop_loss_and_take_profit_triggers():
    rm = RiskManager(RiskConfig(stop_loss_pct=0.02, take_profit_pct=0.04))
    pos = Position(entry_price=100.0, amount=1.0)
    assert rm.should_exit(pos, 99.0) is None
    assert "stop-loss" in rm.should_exit(pos, 97.9)
    assert rm.should_exit(pos, 103.0) is None
    assert "take-profit" in rm.should_exit(pos, 104.1)


def test_daily_loss_cap_blocks_new_positions():
    rm = RiskManager(RiskConfig(max_daily_loss_pct=0.05))
    day = date(2026, 6, 12)
    assert rm.can_open(1000.0, today=day)
    rm.record_trade(-60.0, today=day)  # 6% loss > 5% cap
    assert not rm.can_open(940.0, today=day)
    # A new day resets the cap.
    assert rm.can_open(940.0, today=date(2026, 6, 13))
