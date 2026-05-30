"""
Pattern B/D backtest on M15 historical data.

Signal detection: rolling daily window, one signal per day.
Entry:
  - Pattern B: close of signal bar
  - Pattern D: open of next M15 bar (buffered, as per ST.DEMO spec)
Exit simulation on subsequent M15 bars:
  - TP = entry + 2 * risk  (+2R)
  - SL = stop price        (-1R)
  - Same-bar ambiguity: SL wins
  - Max hold: end of day (last bar of that date)
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
        "open":        "Open",
        "high":        "High",
        "low":         "Low",
        "close":       "Close",
        "tick_volume": "Volume",
    })
    return df[["Open", "High", "Low", "Close", "Volume"]].sort_index()


def simulate_exit(bars: pd.DataFrame, entry: float, sl: float, tp: float) -> dict:
    """Check subsequent bars for SL/TP hit. SL wins on same-bar touch."""
    for ts, bar in bars.iterrows():
        hit_sl = bar["Low"] <= sl
        hit_tp = bar["High"] >= tp
        if hit_sl and hit_tp:
            return {"exit_reason": "SL_HIT", "pnl_r": -1.0, "exit_time": str(ts)}
        if hit_sl:
            return {"exit_reason": "SL_HIT", "pnl_r": -1.0, "exit_time": str(ts)}
        if hit_tp:
            return {"exit_reason": "TP_HIT", "pnl_r": 2.0,  "exit_time": str(ts)}
    return {"exit_reason": "EOD",    "pnl_r":  0.0,  "exit_time": str(bars.index[-1]) if len(bars) else ""}


def run_backtest(symbol: str, min_bars: int = 4) -> list[dict]:
    df = load_m15(symbol)
    print(f"{symbol}: {len(df)} M15 bars  ({df.index[0].date()} to {df.index[-1].date()})")

    trades: list[dict] = []
    dates = sorted(df.index.normalize().unique())

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

            signal_bar_idx = i - 1  # index within day

            if sig["pattern"] == "D_FIRST_PULLBACK":
                # Entry at open of next bar
                if signal_bar_idx + 1 >= len(day):
                    break  # no next bar today
                entry_bar_row = day.iloc[signal_bar_idx + 1]
                entry_time    = str(day.index[signal_bar_idx + 1])
                entry         = round(float(entry_bar_row["Open"]), 5)
                future_bars   = day.iloc[signal_bar_idx + 2:]
                scan_from     = signal_bar_idx + 2
            else:
                # Pattern B: entry at signal bar close
                entry_time  = str(window.index[-1])
                entry       = sig["entry_price"]
                future_bars = day.iloc[signal_bar_idx + 1:]
                scan_from   = signal_bar_idx + 1

            sl   = sig["stop_price"]
            risk = entry - sl
            if risk <= 0:
                i += 1
                continue
            if risk < 20:          # skip tiny overnight stops (< 20 NAS100 pts)
                i += 1
                continue
            tp = round(entry + 2 * risk, 5)

            result = simulate_exit(future_bars, entry, sl, tp)

            trades.append({
                "symbol":       symbol,
                "date":         str(date.date()),
                "pattern":      sig["pattern"],
                "signal_time":  str(window.index[-1]),
                "entry_time":   entry_time,
                "entry":        entry,
                "sl":           sl,
                "tp":           tp,
                "rr":           sig["rr_ratio"],
                **result,
            })

            # Advance past the exit bar so trades don't overlap
            if result["exit_time"] and result["exit_reason"] != "EOD":
                exit_ts = pd.Timestamp(result["exit_time"])
                try:
                    exit_pos = day.index.get_loc(exit_ts)
                    i = exit_pos + 2
                except KeyError:
                    i = len(day) + 1
            else:
                i = len(day) + 1  # EOD or no exit — done for the day

    return trades


def print_results(trades: list[dict], symbol: str) -> None:
    if not trades:
        print(f"  No trades.")
        return

    wins   = [t for t in trades if t["exit_reason"] == "TP_HIT"]
    losses = [t for t in trades if t["exit_reason"] == "SL_HIT"]
    eods   = [t for t in trades if t["exit_reason"] == "EOD"]
    total_r = sum(t["pnl_r"] for t in trades)
    wr      = len(wins) / len(trades) * 100
    gp      = len(wins) * 2
    gl      = len(losses) * 1
    pf      = round(gp / gl, 3) if gl > 0 else float("inf")

    b_trades = [t for t in trades if t["pattern"] == "B_FLAT_TOP"]
    d_trades = [t for t in trades if t["pattern"] == "D_FIRST_PULLBACK"]

    print(f"\n  {symbol} Results")
    print(f"  Trades: {len(trades)}  |  W: {len(wins)}  L: {len(losses)}  EOD: {len(eods)}")
    print(f"  Win rate: {wr:.1f}%  |  Total R: {total_r:+.1f}  |  PF: {pf}")
    print(f"  Pattern B: {len(b_trades)} trades  |  Pattern D: {len(d_trades)} trades")

    for pattern, group in [("B_FLAT_TOP", b_trades), ("D_FIRST_PULLBACK", d_trades)]:
        if not group:
            continue
        gw = sum(1 for t in group if t["exit_reason"] == "TP_HIT")
        gl_ = sum(1 for t in group if t["exit_reason"] == "SL_HIT")
        gr = sum(t["pnl_r"] for t in group)
        gp_ = gw * 2; gg = gl_ * 1
        gpf = round(gp_ / gg, 3) if gg > 0 else float("inf")
        print(f"    {pattern:<20}: {len(group)} trades  W:{gw} L:{gl_}  {gr:+.1f}R  PF:{gpf}")

    # Session breakdown (entry_time UTC)
    def session(entry_time_str: str) -> str:
        h = pd.Timestamp(entry_time_str).hour
        if  0 <= h <  7: return "Asia      00-07"
        if  7 <= h < 13: return "London    07-13"
        if 13 <= h < 17: return "NY Open   13-17"
        if 17 <= h < 21: return "NY Aft    17-21"
        return                   "Overnight 21-24"

    sessions = ["Asia      00-07", "London    07-13", "NY Open   13-17",
                "NY Aft    17-21", "Overnight 21-24"]
    print(f"\n  {'Session':<18} {'N':>4} {'W':>4} {'L':>4} {'EOD':>4} {'WR%':>6} {'R':>7} {'PF':>6}")
    print(f"  {'-'*58}")
    for sess in sessions:
        grp = [t for t in trades if session(t["entry_time"]) == sess]
        if not grp:
            continue
        sw  = sum(1 for t in grp if t["exit_reason"] == "TP_HIT")
        sl  = sum(1 for t in grp if t["exit_reason"] == "SL_HIT")
        se  = sum(1 for t in grp if t["exit_reason"] == "EOD")
        sr  = sum(t["pnl_r"] for t in grp)
        swr = sw / len(grp) * 100
        spf = round(sw * 2 / sl, 3) if sl > 0 else float("inf")
        print(f"  {sess:<18} {len(grp):>4} {sw:>4} {sl:>4} {se:>4} {swr:>5.1f}% {sr:>+7.1f} {spf:>6.3f}")

    print(f"\n  {'Date':<12} {'Session':<16} {'Pattern':<20} {'Entry':>8} {'SL':>8} {'TP':>8} {'Result':<10} {'R':>5}")
    print(f"  {'-'*95}")
    for t in trades:
        print(f"  {t['date']:<12} {session(t['entry_time']):<16} {t['pattern']:<20} "
              f"{t['entry']:>8.4f} {t['sl']:>8.4f} {t['tp']:>8.4f} "
              f"{t['exit_reason']:<10} {t['pnl_r']:>+5.1f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=["NAS100", "EURUSD"])
    args = parser.parse_args()

    all_trades: list[dict] = []
    for sym in args.symbols:
        trades = run_backtest(sym)
        print_results(trades, sym)
        all_trades.extend(trades)

    if len(args.symbols) > 1 and all_trades:
        wins    = sum(1 for t in all_trades if t["exit_reason"] == "TP_HIT")
        losses  = sum(1 for t in all_trades if t["exit_reason"] == "SL_HIT")
        eods    = sum(1 for t in all_trades if t["exit_reason"] == "EOD")
        total_r = sum(t["pnl_r"] for t in all_trades)
        wr      = wins / len(all_trades) * 100
        pf      = round(wins * 2 / losses, 3) if losses > 0 else float("inf")
        print(f"\n  COMBINED: {len(all_trades)} trades  W:{wins} L:{losses} EOD:{eods}"
              f"  WR:{wr:.1f}%  Total R:{total_r:+.1f}  PF:{pf}")

    if all_trades:
        import csv
        out = PROJECT_ROOT / "data" / "reports" / "backtests" / "patbd_nas100_trades.csv"
        fields = ["symbol","date","pattern","signal_time","entry_time","entry","sl","tp","rr","exit_reason","pnl_r","exit_time"]
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(all_trades)
        print(f"\n  Saved: {out}")


if __name__ == "__main__":
    main()
