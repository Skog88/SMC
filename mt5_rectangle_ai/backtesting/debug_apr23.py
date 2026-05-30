"""Debug April 23 PatD signal detection - show when signal fires and entry bar."""
from __future__ import annotations
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
    return df[["Open", "High", "Low", "Close", "Volume"]].sort_index()

df = load_m15("NAS100")

TARGET_DATE = pd.Timestamp("2026-04-23", tz="UTC")
day = df[df.index.normalize() == TARGET_DATE]
print(f"April 23 bars: {len(day)}")

for i in range(4, len(day) + 1):
    window = day.iloc[:i]
    sig = check_entry_signal(window)
    if not sig:
        continue
    signal_bar_time = window.index[-1]
    entry_bar_time  = day.index[i] if i < len(day) else None
    risk = sig["entry_price"] - sig["stop_price"]
    if risk < 20:
        print(f"  i={i:2d}  signal={signal_bar_time.strftime('%H:%M')}  SKIPPED risk={risk:.1f}")
        continue
    print(f"  i={i:2d}  signal_bar={signal_bar_time.strftime('%H:%M')}  "
          f"entry_bar={entry_bar_time.strftime('%H:%M') if entry_bar_time else 'EOD'}  "
          f"entry={sig['entry_price']}  stop={sig['stop_price']}  risk={risk:.1f}")
    print(f"  ACCEPTED - this is the trade backtest uses")
    break

print()
print("Bars around 08:30-10:00:")
for ts, row in day.iterrows():
    if ts.hour < 8 or ts.hour > 10:
        continue
    color = "G" if row["Close"] > row["Open"] else "R"
    print(f"  {ts.strftime('%H:%M')} {color}  O={row['Open']:.2f} H={row['High']:.2f} L={row['Low']:.2f} C={row['Close']:.2f}")
