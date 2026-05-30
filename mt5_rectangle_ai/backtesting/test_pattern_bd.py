"""
Quick test of Pattern B/D detection on downloaded M15 historical data.

Runs check_entry_signal on a rolling session window for each bar in each day.
Session window: first bar of the day up to current bar (simulates live scan).
Reports all detected signals with date, pattern, entry, stop, RR.
"""

from __future__ import annotations

import argparse
import pandas as pd
from pathlib import Path
from zoneinfo import ZoneInfo

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategy.pattern_bd import check_entry_signal

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UTC = ZoneInfo("UTC")


def load_m15(symbol: str) -> pd.DataFrame:
    path = PROJECT_ROOT / "data" / "historical" / symbol / "M15.csv"
    df = pd.read_csv(path, parse_dates=["time"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time")
    df = df.rename(columns={
        "open":  "Open",
        "high":  "High",
        "low":   "Low",
        "close": "Close",
        "tick_volume": "Volume",
    })
    return df[["Open", "High", "Low", "Close", "Volume"]].sort_index()


def run_test(symbol: str, min_bars: int = 4) -> list[dict]:
    df = load_m15(symbol)
    print(f"\n{symbol}: {len(df)} M15 bars  ({df.index[0].date()} to {df.index[-1].date()})")

    signals: list[dict] = []
    dates = sorted(df.index.normalize().unique())

    for date in dates:
        day = df[df.index.normalize() == date]
        if len(day) < min_bars:
            continue

        for i in range(min_bars, len(day) + 1):
            window = day.iloc[:i]
            sig = check_entry_signal(window)
            if sig:
                signals.append({
                    "symbol":    symbol,
                    "date":      str(date.date()),
                    "bar_time":  str(window.index[-1]),
                    "pattern":   sig["pattern"],
                    "entry":     sig["entry_price"],
                    "stop":      sig["stop_price"],
                    "target":    sig["target_price"],
                    "rr":        sig["rr_ratio"],
                    "vol_ratio": sig.get("vol_ratio", ""),
                    "reason":    sig["reason"],
                })
                break  # one signal per day

    return signals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=["NAS100", "EURUSD"])
    args = parser.parse_args()

    all_signals: list[dict] = []
    for sym in args.symbols:
        sigs = run_test(sym)
        all_signals.extend(sigs)

    if not all_signals:
        print("\nNo signals detected.")
        return

    print(f"\n{'-'*90}")
    print(f"{'Date':<12} {'Sym':<8} {'Pattern':<18} {'Bar time':<22} {'Entry':>8} {'Stop':>8} {'Target':>8} {'R:R':>5} {'Vol':>5}")
    print(f"{'-'*90}")
    for s in all_signals:
        print(f"{s['date']:<12} {s['symbol']:<8} {s['pattern']:<18} {s['bar_time']:<22} "
              f"{s['entry']:>8.4f} {s['stop']:>8.4f} {s['target']:>8.4f} "
              f"{s['rr']:>5.2f} {str(s['vol_ratio']):>5}")

    b_count = sum(1 for s in all_signals if s["pattern"] == "B_FLAT_TOP")
    d_count = sum(1 for s in all_signals if s["pattern"] == "D_FIRST_PULLBACK")
    print(f"{'-'*90}")
    print(f"Total: {len(all_signals)} signals  |  Pattern B: {b_count}  |  Pattern D: {d_count}")


if __name__ == "__main__":
    main()
