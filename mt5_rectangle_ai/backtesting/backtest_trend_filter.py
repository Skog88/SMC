"""
Trend filter comparison for Pattern D backtest.

Tests three uptrend filters against the unfiltered baseline:
  A. MA filter    — signal bar close > N-period SMA
  B. Net momentum — signal bar close > close[N bars ago]
  C. Prev day high — signal bar close > previous day high

Runs all combinations and prints a comparison table.
"""

from __future__ import annotations

import argparse
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategy.pattern_bd import check_entry_signal

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_m15(symbol: str) -> pd.DataFrame:
    path = PROJECT_ROOT / "data" / "historical" / symbol / "M15.csv"
    df = pd.read_csv(path, parse_dates=["time"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time")
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "tick_volume": "Volume",
    })
    df = df[["Open", "High", "Low", "Close", "Volume"]].sort_index()
    # Pre-compute indicators on the full dataset
    for n in [8, 12, 16, 20, 50]:
        df[f"ma{n}"] = df["Close"].rolling(n).mean()
    return df


def simulate_exit(bars: pd.DataFrame, entry: float, sl: float, tp: float,
                  be_r: float = 0.0, tp_r: float = 2.0,
                  lock_r: float = 0.0, lock_trigger_r: float = 0.0) -> dict:
    """
    be_r:            move stop to entry (0R) when High >= entry + be_r * risk.
    lock_r/lock_trigger_r: move stop to entry + lock_r*risk when High >= entry + lock_trigger_r*risk.
                     e.g. lock_r=1.0, lock_trigger_r=2.0 = lock in +1R when +2R reached.
    BE takes priority if both set. Set only one.
    """
    risk        = entry - sl
    be_hit      = False
    lock_hit    = False
    current_sl  = sl

    for ts, bar in bars.iterrows():
        # Check lock-in trigger
        if lock_trigger_r > 0 and not lock_hit and bar["High"] >= entry + lock_trigger_r * risk:
            lock_hit   = True
            current_sl = entry + lock_r * risk
        # Check BE trigger
        if be_r > 0 and not be_hit and bar["High"] >= entry + be_r * risk:
            be_hit     = True
            current_sl = entry

        hit_sl = bar["Low"] <= current_sl
        hit_tp = bar["High"] >= tp

        if hit_sl and hit_tp:
            if lock_hit:
                return {"exit_reason": "LOCK_HIT", "pnl_r": lock_r,  "exit_time": str(ts)}
            if be_hit:
                return {"exit_reason": "BE_HIT",   "pnl_r": 0.0,     "exit_time": str(ts)}
            return     {"exit_reason": "SL_HIT",   "pnl_r": -1.0,    "exit_time": str(ts)}
        if hit_sl:
            if lock_hit:
                return {"exit_reason": "LOCK_HIT", "pnl_r": lock_r,  "exit_time": str(ts)}
            if be_hit:
                return {"exit_reason": "BE_HIT",   "pnl_r": 0.0,     "exit_time": str(ts)}
            return     {"exit_reason": "SL_HIT",   "pnl_r": -1.0,    "exit_time": str(ts)}
        if hit_tp:
            return     {"exit_reason": "TP_HIT",   "pnl_r": tp_r,    "exit_time": str(ts)}

    return {"exit_reason": "EOD", "pnl_r": 0.0,
            "exit_time": str(bars.index[-1]) if len(bars) else ""}


def run_filtered(df: pd.DataFrame, filter_fn, min_bars: int = 4,
                 be_r: float = 0.0, tp_r: float = 2.0,
                 min_risk: float = 20.0,
                 lock_r: float = 0.0, lock_trigger_r: float = 0.0,
                 return_trades: bool = False):
    """Run backtest applying filter_fn(df, signal_bar_pos) -> bool before entering."""
    trades = []
    dates  = sorted(df.index.normalize().unique())

    for date in dates:
        day = df[df.index.normalize() == date]
        if len(day) < min_bars:
            continue

        i = min_bars
        while i <= len(day):
            window = day.iloc[:i]
            sig = check_entry_signal(window)
            if not sig:
                i += 1
                continue

            signal_bar_idx = i - 1

            if sig["pattern"] == "D_FIRST_PULLBACK":
                if signal_bar_idx + 1 >= len(day):
                    break
                entry_bar_row = day.iloc[signal_bar_idx + 1]
                entry_time    = str(day.index[signal_bar_idx + 1])
                entry         = round(float(entry_bar_row["Open"]), 5)
                future_bars   = day.iloc[signal_bar_idx + 2:]
                scan_from     = signal_bar_idx + 2
            else:
                entry_time  = str(window.index[-1])
                entry       = sig["entry_price"]
                future_bars = day.iloc[signal_bar_idx + 1:]
                scan_from   = signal_bar_idx + 1

            sl   = sig["stop_price"]
            risk = entry - sl
            if risk <= 0 or risk < min_risk:
                i += 1
                continue

            # Apply trend filter — uses full df position of signal bar
            signal_ts  = window.index[-1]
            signal_pos = df.index.get_loc(signal_ts)
            if not filter_fn(df, signal_pos):
                i += 1
                continue

            tp     = round(entry + 2 * risk, 5)
            actual_tp = round(entry + tp_r * risk, 5)
            result = simulate_exit(future_bars, entry, sl, actual_tp,
                                   be_r=be_r, tp_r=tp_r,
                                   lock_r=lock_r, lock_trigger_r=lock_trigger_r)

            trades.append({
                "date":        str(window.index[-1].date()),
                "pattern":     sig["pattern"],
                "signal_time": str(window.index[-1]),
                "entry_time":  entry_time,
                "entry":       entry,
                "sl":          sig["stop_price"],
                "tp":          round(entry + tp_r * (entry - sig["stop_price"]), 5),
                "pnl_r":       result["pnl_r"],
                "exit_reason": result["exit_reason"],
                "exit_time":   result["exit_time"],
            })

            if result["exit_time"] and result["exit_reason"] != "EOD":
                exit_ts = pd.Timestamp(result["exit_time"])
                try:
                    exit_pos = day.index.get_loc(exit_ts)
                    i = exit_pos + 2
                except KeyError:
                    i = len(day) + 1
            else:
                i = len(day) + 1

    if not trades:
        empty = {"n": 0, "w": 0, "l": 0, "eod": 0, "r": 0.0, "wr": 0.0, "pf": 0.0}
        return (empty, []) if return_trades else empty

    w    = sum(1 for t in trades if t["exit_reason"] == "TP_HIT")
    l    = sum(1 for t in trades if t["exit_reason"] == "SL_HIT")
    be   = sum(1 for t in trades if t["exit_reason"] == "BE_HIT")
    lock = sum(1 for t in trades if t["exit_reason"] == "LOCK_HIT")
    eod  = sum(1 for t in trades if t["exit_reason"] == "EOD")
    r    = sum(t["pnl_r"] for t in trades)
    wr   = w / len(trades) * 100
    pf   = round(w * tp_r / l, 3) if l > 0 else float("inf")
    stats = {"n": len(trades), "w": w, "l": l, "be": be, "lock": lock,
             "eod": eod, "r": r, "wr": wr, "pf": pf}
    return (stats, trades) if return_trades else stats


def fmt(res: dict) -> str:
    be  = res.get("be", 0)
    eod = res.get("eod", 0)
    return (f"N={res['n']:3d}  W={res['w']:3d}  L={res['l']:3d}  "
            f"BE={be:3d}  WR={res['wr']:5.1f}%  R={res['r']:+6.1f}  PF={res['pf']:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="NAS100")
    args = parser.parse_args()

    df = load_m15(args.symbol)
    print(f"\n{args.symbol}: {len(df)} M15 bars  "
          f"({df.index[0].date()} to {df.index[-1].date()})\n")

    # Winning filter: Asia+London + momentum N=6
    def best_filter(df, pos):
        h = df.index[pos].hour
        return 0 <= h < 13 and pos >= 6 and df["Close"].iloc[pos] > df["Close"].iloc[pos - 6]

    tp_levels = [2.0, 2.5, 2.75, 3.0, 3.25, 3.5]
    be_levels = [0.0, 0.5, 1.0, 1.5]

    # Header
    col_w = 28
    header = f"  {'TP \\ BE':<10}" + "".join(f"  {'BE@'+str(b)+'R':<{col_w}}" for b in be_levels)
    print(header)
    print("  " + "-" * (10 + len(be_levels) * (col_w + 2)))

    for tp in tp_levels:
        row = f"  {f'TP={tp}R':<10}"
        for be in be_levels:
            res = run_filtered(df, best_filter, be_r=be, tp_r=tp)
            cell = f"N={res['n']} W={res['w']} L={res['l']} BE={res['be']} R={res['r']:+.0f} PF={res['pf']:.3f}"
            row += f"  {cell:<{col_w}}"
        print(row)

    print()
    print("  Best R per TP (across all BE levels):")
    print(f"  {'TP':>6}  {'BE':>6}  {'N':>4}  {'W':>4}  {'L':>4}  {'BE_cnt':>6}  {'WR%':>6}  {'R':>7}  {'PF':>6}")
    print(f"  {'-'*65}")
    for tp in tp_levels:
        best = max(
            (run_filtered(df, best_filter, be_r=be, tp_r=tp) | {"be_trig": be} for be in be_levels),
            key=lambda r: r["r"]
        )
        print(f"  {tp:>6.2f}  {best['be_trig']:>6.1f}  {best['n']:>4}  {best['w']:>4}  "
              f"{best['l']:>4}  {best['be']:>6}  {best['wr']:>5.1f}%  "
              f"{best['r']:>+7.1f}  {best['pf']:>6.3f}")

    # ── Save final config trades to CSV ──────────────────────────────────────
    FINAL_TP = 3.0
    FINAL_BE = 2.0
    print(f"\n  Saving final config (TP={FINAL_TP}R  BE@{FINAL_BE}R) trades to CSV...")
    _, final_trades = run_filtered(df, best_filter, be_r=FINAL_BE, tp_r=FINAL_TP,
                                   return_trades=True)
    import csv
    out = PROJECT_ROOT / "data" / "reports" / "backtests" / "patbd_nas100_filtered_trades.csv"
    fields = ["date", "pattern", "signal_time", "entry_time", "entry", "sl", "tp",
              "pnl_r", "exit_reason", "exit_time"]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(final_trades)
    print(f"  Saved {len(final_trades)} trades -> {out}")


if __name__ == "__main__":
    main()
