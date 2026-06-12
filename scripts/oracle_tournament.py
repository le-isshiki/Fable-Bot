"""Tournament of 50 omniscient traders, each with a different self-imposed style.

Every trader sees the future with 100% certainty: they never enter a trade
whose outcome they don't already know. What differs is the strategy each has
"built from experience": how long they hold, how selective they are, which
hours they trade, how much of their balance they commit, and whether they
feel compelled to trade even on bad days.

All start with $50, trade one symbol on hourly bars for 30 days (720 bars),
and pay 0.1% fees per side.

After ranking, the winner's strategy is re-run with *imperfect* foresight
(direction predicted correctly only p% of the time) to show how the strategy
behaves the moment its one real ingredient — knowing the future — is replaced
by the best accuracy achievable without magic.

Usage:
    python scripts/oracle_tournament.py path/to/candles_1h.csv
"""

import os
import random
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fable_bot.data import load_csv

FEE = 0.001          # per side
START = 50.0
BARS = 720           # 30 days of hourly candles

SESSIONS = {
    "Asia session": range(0, 8),
    "Europe session": range(7, 15),
    "US session": range(13, 21),
    "night owl": list(range(21, 24)) + list(range(0, 5)),
}

NAMES = [
    "Akira", "Bianca", "Carlos", "Dmitri", "Elena", "Farid", "Greta", "Hiro",
    "Ines", "Jonas", "Kemi", "Liang", "Mara", "Nadia", "Omar", "Priya",
    "Quentin", "Rosa", "Sven", "Tunde", "Uma", "Viktor", "Wanda", "Xavier",
    "Yuki", "Zara", "Abebe", "Brigitte", "Chen", "Dalia", "Emil", "Fatima",
    "Gustav", "Hana", "Igor", "Jamila", "Klaus", "Leila", "Marco", "Noor",
    "Otto", "Paloma", "Rafael", "Sofia", "Tariq", "Ulrike", "Vera", "Wei",
    "Yusuf", "Zofia",
]


@dataclass
class Trader:
    name: str
    style: str
    kind: str = "lookahead"   # lookahead | daily_best | forced | buy_hold
    max_hold: int = 1         # longest position, in bars
    threshold: float = 0.0    # minimum net return required to enter
    fraction: float = 1.0     # share of balance committed per trade
    hours: object = None      # restrict entries to these hours of day
    trades_per_day: int = 0   # for daily_best/forced kinds
    # results
    balance: float = START
    trades: int = 0
    wins: int = 0
    trade_returns: list = field(default_factory=list)

    @property
    def win_rate(self):
        return self.wins / self.trades if self.trades else 0.0

    def record(self, net):
        self.balance += self.balance * self.fraction * net
        self.trades += 1
        self.wins += net > 0
        self.trade_returns.append(net)


def build_traders() -> list[Trader]:
    traders = []

    def add(style, **kw):
        traders.append(Trader(name=NAMES[len(traders)], style=style, **kw))

    # 8 scalpers: hold exactly 1 bar, varying selectivity
    for thr in [0.0, 0.001, 0.002, 0.003, 0.005, 0.008, 0.012, 0.02]:
        add(f"scalper, 1-bar hold, min move {thr:.1%}", max_hold=1, threshold=thr)

    # 15 swing traders: flexible hold up to N bars, varying selectivity
    for mh in [4, 8, 12, 24, 48]:
        for thr in [0.0, 0.005, 0.02]:
            add(f"swing, hold<= {mh}h, min move {thr:.1%}", max_hold=mh, threshold=thr)

    # 8 session traders: only enter during their preferred hours
    for sess, hours in SESSIONS.items():
        for mh in (1, 6):
            add(f"{sess} only, hold<={mh}h", max_hold=mh, hours=set(hours))

    # 5 cautious sizers: commit only part of the balance per trade
    for frac in [0.10, 0.25, 0.50, 0.75, 0.90]:
        add(f"risk-managed, {frac:.0%} of balance, hold<=12h",
            max_hold=12, threshold=0.002, fraction=frac)

    # 4 frequency-capped: only their N favorite (best) trades each day
    for cap in [1, 2, 3, 5]:
        add(f"picky, best {cap} trade(s)/day", kind="daily_best", trades_per_day=cap)

    # 3 compulsive over-traders: MUST place N trades a day, even on bad days
    for cap in [3, 6, 12]:
        add(f"compulsive, forced {cap} trades/day", kind="forced", trades_per_day=cap)

    # 1 buy-and-hold believer
    add("diamond hands: buy day 1, sell day 30", kind="buy_hold")

    # 3 dip buyers: only enter right after a red candle
    for mh in [2, 6, 12]:
        add(f"dip buyer, enters after red bar, hold<={mh}h",
            max_hold=mh, threshold=0.002, hours=None, kind="dip")

    # 3 hybrid veterans: selective swing + partial sizing + session limits
    veterans = [
        (24, 0.01, 0.75, None),
        (12, 0.005, 0.50, "Europe session"),
        (8, 0.003, 0.90, "US session"),
    ]
    for mh, thr, frac, sess in veterans:
        hours = set(SESSIONS[sess]) if sess else None
        label = f", {sess} only" if sess else ""
        add(f"veteran: hold<={mh}h, min {thr:.1%}, {frac:.0%} sized{label}",
            max_hold=mh, threshold=thr, fraction=frac, hours=hours)

    assert len(traders) == 50, len(traders)
    return traders


def net_return(closes, i, h):
    return closes[i + h] / closes[i] * (1 - FEE) ** 2 - 1


def simulate(trader: Trader, closes: list[float]) -> None:
    n = len(closes)

    if trader.kind == "buy_hold":
        trader.record(net_return(closes, 0, n - 1))
        return

    if trader.kind in ("daily_best", "forced"):
        for day_start in range(0, n - 1, 24):
            day_nets = [(net_return(closes, i, 1), i)
                        for i in range(day_start, min(day_start + 24, n - 1))]
            day_nets.sort(reverse=True)
            for rank in range(min(trader.trades_per_day, len(day_nets))):
                net, _ = day_nets[rank]
                if trader.kind == "daily_best" and net <= 0:
                    break  # the picky trader simply stays out
                trader.record(net)  # the forced trader takes it regardless
        return

    i = 0
    while i < n - 1:
        hour = i % 24
        if trader.hours is not None and hour not in trader.hours:
            i += 1
            continue
        if trader.kind == "dip" and not (i > 0 and closes[i] < closes[i - 1]):
            i += 1
            continue
        # Perfect foresight: inspect every allowed holding period, take the best.
        best_h, best_net = 0, trader.threshold
        for h in range(1, min(trader.max_hold, n - 1 - i) + 1):
            net = net_return(closes, i, h)
            if net > best_net:
                best_h, best_net = h, net
        if best_h:
            trader.record(best_net)
            i += best_h
        else:
            i += 1


def degrade_foresight(closes, accuracy, fraction=1.0, runs=300, seed=1):
    """The winner's style with imperfect prediction: each bar the predicted
    direction is correct with probability `accuracy`; trader goes all-in on
    predicted-up bars (1-bar hold). Returns median final balance."""
    rng = random.Random(seed)
    finals = []
    rets = [closes[i + 1] / closes[i] - 1 for i in range(len(closes) - 1)]
    for _ in range(runs):
        bal = START
        for r in rets:
            actual_up = r > 0
            predicted_up = actual_up if rng.random() < accuracy else not actual_up
            if predicted_up:
                bal += bal * fraction * ((1 + r) * (1 - FEE) ** 2 - 1)
        finals.append(bal)
    finals.sort()
    return finals[len(finals) // 2]


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    candles = load_csv(sys.argv[1])
    if len(candles) < BARS:
        sys.exit(f"need at least {BARS} candles, got {len(candles)}")
    closes = [c[4] for c in candles[-BARS:]]
    market = closes[-1] / closes[0] - 1

    traders = build_traders()
    for t in traders:
        simulate(t, closes)
    traders.sort(key=lambda t: t.balance, reverse=True)

    print(f"50 perfect-foresight traders | $50 start | 30 days (720 hourly bars) | "
          f"0.1% fees/side | market itself moved {market:+.1%}\n")
    print(f"{'#':>2} {'trader':<10} {'style':<55} {'final $':>9} {'return':>8} "
          f"{'trades':>6} {'win%':>5}")
    for rank, t in enumerate(traders, 1):
        print(f"{rank:>2} {t.name:<10} {t.style:<55} {t.balance:>9.2f} "
              f"{t.balance / START - 1:>7.1%} {t.trades:>6} {t.win_rate:>5.0%}")

    w = traders[0]
    daily = (w.balance / START) ** (1 / 30) - 1
    avg = sum(w.trade_returns) / len(w.trade_returns)
    print(f"\n=== Winner: {w.name} ({w.style}) ===")
    print(f"Final balance: ${w.balance:.2f} ({w.balance / START - 1:+.1%} in 30 days, "
          f"{daily:+.2%}/day compounded)")
    print(f"Trades: {w.trades}  Win rate: {w.win_rate:.0%}  "
          f"Avg net/trade: {avg:+.2%}  Best: {max(w.trade_returns):+.2%}")

    print("\n=== The winner's strategy WITHOUT magic ===")
    print("Same style, but direction is *predicted* instead of known.")
    print("(55% accuracy would already make you one of the best forecasters alive;")
    print(" published academic models rarely sustain >52-53% on hourly crypto.)\n")
    for acc in [1.0, 0.60, 0.55, 0.52, 0.50]:
        final = degrade_foresight(closes, acc)
        label = {1.0: "omniscient", 0.60: "impossible-good", 0.55: "world-class",
                 0.52: "excellent real model", 0.50: "coin flip"}[acc]
        print(f"  {acc:.0%} accuracy ({label:<20}): $50 -> ${final:>10.2f}")


if __name__ == "__main__":
    main()
