"""Candle data loading from CSV files or the exchange.

CSV format: timestamp,open,high,low,close,volume — one candle per row,
oldest first, with or without a header row. Timestamps in ms or seconds.
"""

import csv


def load_csv(path: str) -> list[list[float]]:
    candles: list[list[float]] = []
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if not row:
                continue
            try:
                values = [float(x) for x in row[:6]]
            except ValueError:
                continue  # header row
            if len(values) < 6:
                raise ValueError(f"{path}: expected 6 columns (ts,o,h,l,c,v), got {len(values)}")
            if values[0] < 1e12:  # seconds -> milliseconds
                values[0] *= 1000
            candles.append(values)
    if not candles:
        raise ValueError(f"{path}: no candle rows found")
    return candles


def save_csv(path: str, candles: list[list[float]]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerows(candles)
