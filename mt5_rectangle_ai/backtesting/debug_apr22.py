"""Debug why April 22 08:45 UTC PatD setup is not detected at that bar."""
from __future__ import annotations
import pandas as pd
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategy.pattern_bd import check_entry_signal, _session_to_patd_df, _detect_pattern_d

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
    return df[["Open", "High", "Low", "Close", "Volume"]].sort_index()

df = load_m15("NAS100")

TARGET_DATE = pd.Timestamp("2026-04-23", tz="UTC")
day = df[df.index.normalize() == TARGET_DATE]

# Trace i=36 (window includes 08:45 bar at index 35) in detail
i = 36
window = day.iloc[:i]
patd_df = _session_to_patd_df(window)
n = len(patd_df)

opens   = patd_df["open"].values.astype(float)
closes  = patd_df["close"].values.astype(float)
highs   = patd_df["high"].values.astype(float)
lows    = patd_df["low"].values.astype(float)
times   = pd.to_datetime(patd_df["datetime"])

print(f"Window i={i}, n={n}, last bar = {times.iloc[-1].strftime('%H:%M')}")
print()

# Scan for pullbacks the same way _detect_pattern_d does
j = 1
while j < n:
    if lows[j] >= lows[j - 1]:
        j += 1
        continue

    pb_start = j
    k = j + 1
    while k < n and lows[k] <= lows[k - 1]:
        k += 1

    pb_end = k
    pb_len = pb_end - pb_start
    pb_low = float(lows[pb_start:pb_end].min())

    flagpole_base   = float(lows[0])
    flagpole_top    = float(highs[:pb_start].max())
    flagpole_height = flagpole_top - flagpole_base
    retrace_pct = ((flagpole_top - pb_low) / flagpole_height * 100) if flagpole_height > 0 else 0
    passes_retrace = pb_low >= flagpole_top - 0.5 * flagpole_height

    print(f"  Pullback pb_start={pb_start}({times.iloc[pb_start].strftime('%H:%M')}) "
          f"pb_end={pb_end}({times.iloc[min(pb_end,n-1)].strftime('%H:%M')}) "
          f"pb_len={pb_len} pb_low={pb_low:.2f}")
    print(f"    flagpole_base={flagpole_base:.2f} flagpole_top={flagpole_top:.2f} "
          f"height={flagpole_height:.2f} retrace={retrace_pct:.1f}% "
          f"passes_50pct={passes_retrace}")

    if pb_len < 2:
        print(f"    SKIP: pb_len < 2")
        j = pb_start + 1
        continue

    if not passes_retrace:
        print(f"    SKIP: >50% retrace")
        j = pb_end
        continue

    # Scan for signal bar
    print(f"    Scanning for signal bar from k={pb_end} to {n-1}...")
    for sig_k in range(pb_end, n):
        t_offset = int((times.iloc[min(sig_k+1, n-1)] - times.iloc[0]).total_seconds() / 60)
        is_last = (sig_k == n - 1)
        is_green = closes[sig_k] > opens[sig_k]
        higher_high = highs[sig_k] > highs[sig_k - 1]
        print(f"      k={sig_k}({times.iloc[sig_k].strftime('%H:%M')}) "
              f"green={is_green} higher_high={higher_high} "
              f"t_offset={t_offset}min is_last={is_last}")
        if sig_k + 1 < n and t_offset > 110:
            print(f"      BREAK: time > 110 min")
            break
        if is_green and higher_high:
            print(f"      SIGNAL BAR FOUND at k={sig_k}")
            break
    j = pb_end

print()
print("Summary: 50% retrace check fails for the 08:00-08:30 pullback because")
print("flagpole_base=lows[0] (midnight bar) gives wrong flagpole base.")
print("08:45 bar: green, high=26690.53 > prior high=26689.03 -- should be valid signal")
