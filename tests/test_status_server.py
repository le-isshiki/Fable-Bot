import json
import urllib.request

from fable_bot.config import Config, ExchangeConfig
from fable_bot.status_server import start_status_server
from fable_bot.trader import Trader

from tests.test_state import FakeExchange


def test_status_endpoint_reports_bot_state():
    cfg = Config()
    cfg.exchange = ExchangeConfig(testnet=True)
    trader = Trader(cfg, FakeExchange(dry_run=True))
    server = start_status_server(trader, port=0)  # OS-assigned free port
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
            payload = json.loads(resp.read())
        assert payload["status"] == "running"
        assert payload["mode"] == "dry-run"
        assert payload["strategy"] == cfg.strategy.name
        assert payload["position"] is None
        assert payload["paper_balances"]["QUOTE"] == 1000.0
    finally:
        server.shutdown()
