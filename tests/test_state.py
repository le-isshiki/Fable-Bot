"""State persistence: positions and risk state survive restarts, safely."""

import json

from fable_bot.config import Config, ExchangeConfig
from fable_bot.state import StateStore
from fable_bot.trader import Trader


class FakeExchange:
    """Just enough of the Exchange interface for Trader unit tests."""

    def __init__(self, dry_run=True, base=0.0, quote=1000.0):
        self.dry_run = dry_run
        self._paper = {"BASE": base, "QUOTE": quote}

    def balances(self, symbol):
        return self._paper["BASE"], self._paper["QUOTE"]

    def paper_balances(self):
        return dict(self._paper)

    def set_paper_balances(self, balances):
        self._paper.update(balances)

    def market_buy(self, symbol, quote_amount):
        price = 100.0
        amount = quote_amount / price
        self._paper["QUOTE"] -= quote_amount
        self._paper["BASE"] += amount
        return {"price": price, "amount": amount}

    def market_sell(self, symbol, base_amount):
        price = 100.0
        self._paper["BASE"] -= base_amount
        self._paper["QUOTE"] += base_amount * price
        return {"price": price, "amount": base_amount}


def make_trader(tmp_path, dry_run=True, base=0.0, testnet=True):
    cfg = Config()
    cfg.exchange = ExchangeConfig(testnet=testnet)
    store = StateStore(str(tmp_path / "state.json"))
    exchange = FakeExchange(dry_run=dry_run, base=base)
    return Trader(cfg, exchange, store=store), store


def test_store_roundtrip_and_corruption(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.load() == {}
    store.save({"a": 1})
    assert store.load() == {"a": 1}
    with open(store.path, "w") as f:
        f.write("{not json")
    assert store.load() == {}


def test_position_survives_restart(tmp_path):
    trader, store = make_trader(tmp_path)
    trader._open(100.0)
    assert trader.position is not None

    reborn, _ = make_trader(tmp_path)
    assert reborn.position is not None
    assert reborn.position.entry_price == trader.position.entry_price
    assert reborn.position.amount == trader.position.amount
    # Paper balances came back too, so the paper session continues seamlessly.
    assert reborn.exchange.paper_balances() == trader.exchange.paper_balances()


def test_close_clears_persisted_position(tmp_path):
    trader, _ = make_trader(tmp_path)
    trader._open(100.0)
    trader._close(100.0)

    reborn, _ = make_trader(tmp_path)
    assert reborn.position is None


def test_dry_run_state_never_leaks_into_live(tmp_path):
    trader, store = make_trader(tmp_path)
    trader._open(100.0)

    live, _ = make_trader(tmp_path, dry_run=False, base=1.0)
    assert live.position is None, "dry-run state must not be restored into a live trader"


def test_live_position_reconciles_with_exchange_balance(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    store.save({
        "mode": "testnet",
        "symbol": "BTC/USDT",
        "position": {"entry_price": 100.0, "amount": 1.0},
        "risk": {},
        "paper": None,
    })

    # Exchange only holds half the recorded amount: clamp.
    cfg = Config()
    cfg.exchange = ExchangeConfig(testnet=True)
    clamped = Trader(cfg, FakeExchange(dry_run=False, base=0.5), store=store)
    assert clamped.position is not None
    assert clamped.position.amount == 0.5

    # Exchange holds nothing: the position was closed manually, drop it.
    dropped = Trader(cfg, FakeExchange(dry_run=False, base=0.0), store=store)
    assert dropped.position is None


def test_daily_loss_state_survives_restart(tmp_path):
    trader, _ = make_trader(tmp_path)
    trader.risk.can_open(1000.0)          # anchors today's starting equity
    trader.risk.record_trade(-100.0)      # -10%, beyond the 5% daily cap
    trader._save_state()

    reborn, _ = make_trader(tmp_path)
    assert reborn.risk.can_open(900.0) is False, "daily loss cap must survive a restart"
