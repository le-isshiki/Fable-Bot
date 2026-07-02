"""Crash-safe persistence for the trader's open position and daily risk state.

Without this, a restart while holding a position would make the bot forget
it owns anything: the stop-loss would never fire and the coins would sit
unmanaged. State is written atomically (write temp file, then rename) so a
crash mid-write can't corrupt the previous good state.
"""

import json
import logging
import os

log = logging.getLogger(__name__)


class StateStore:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            log.exception("Could not read state file %s; starting fresh", self.path)
            return {}

    def save(self, state: dict) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, self.path)
