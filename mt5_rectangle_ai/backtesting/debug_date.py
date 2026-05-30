"""Debug PatD signal detection for any date."""
from __future__ import annotations
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategy.pattern_bd import check_entry_signal, _session_to_patd_df, _detect_pattern_d

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_DATE  = sys.argv[1] if len(sys.argv) > 1 else "2026-04-15"

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
date = pd.Timestamp(TARGET_DATE, tz="UTC")
day  = df[df.index.normalize() == date]
print(f"{TARGET_DATE}: {len(day)} bars\n")

# Print all bars with time for reference
for pos, (ts, row) in enumerate(day.iterrows()):
    c = "G" if row["Close"] > row["Open"] else "R"
    print(f"  [{pos:2d}] {ts.strftime('%H:%M')} {c}  O={row['Open']:.2f} H={row['High']:.2f} L={row['Low']:.2f} C={row['Close']:.2f}")

print()
print("=== Signal scan ===")

# Scan every window and print when check_entry_signal fires
for i in range(4, len(day) + 1):
    window = day.iloc[:i]
    sig = check_entry_signal(window)
    if not sig:
        continue
    bar_time = window.index[-1].strftime("%H:%M")
    risk = sig["entry_price"] - sig["stop_price"]
    status = "SKIP<20" if risk < 20 else "SIGNAL"
    print(f"  i={i:2d} [{i-1:2d}] {bar_time}  {sig['pattern']:<20}  "
          f"entry={sig['entry_price']}  sl={sig['stop_price']}  risk={risk:.1f}  {status}")
