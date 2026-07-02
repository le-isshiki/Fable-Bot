"""Tiny HTTP status endpoint.

Two jobs: it lets the bot deploy on PaaS free tiers that only accept web
services (Koyeb and friends health-check a port and sleep services that get
no traffic — point a free uptime pinger at this and the bot stays awake),
and it gives you a URL to check the bot from a phone.
"""

import json
import logging
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)

_STARTED_AT = time.time()


def start_status_server(trader, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = {
                "status": "running",
                "uptime_seconds": int(time.time() - _STARTED_AT),
                "mode": trader._mode(),
                "symbol": trader.cfg.trading.symbol,
                "timeframe": trader.cfg.trading.timeframe,
                "strategy": trader.cfg.strategy.name,
                "strategy_params": trader.cfg.strategy.params,
                "position": asdict(trader.position) if trader.position else None,
                "paper_balances": trader.exchange.paper_balances()
                if trader.exchange.dry_run else None,
            }
            body = json.dumps(payload, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # keep request noise out of trade logs
            pass

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True, name="status-server").start()
    log.info("Status server listening on port %d", server.server_address[1])
    return server
