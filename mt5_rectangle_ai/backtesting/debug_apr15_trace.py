"""Trace exactly what _detect_pattern_d returns for April 15 window ending at 17:00."""
from __future__ import annotations
import pandas as pd
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
date = pd.Timestamp("2026-04-15", tz="UTC")
day  = df[df.index.normalize() == date]

# Window ending at bar 68 (17:00) = i=69
for i in [69, 70]:
    window = day.iloc[:i]
    patd_df = _session_to_patd_df(window)
    signals = _detect_pattern_d(patd_df)
    n = len(patd_df)
    print(f"i={i}  n={n}  last_bar={patd_df['datetime'].iloc[-1].strftime('%H:%M')}  signals={len(signals)}")
    for s in signals:
        sig_time = patd_df['datetime'].iloc[s['_signal_bar']].strftime('%H:%M')
        print(f"  sig_bar={s['_signal_bar']}({sig_time})  is_last={s['_signal_bar']==n-1}  "
              f"entry={s['entry']}  stop={s['stop']}")
    sig = check_entry_signal(window)
    latest = window.iloc[-1]
    print(f"  latest green: {latest['Close'] > latest['Open']}  "
          f"check_entry_signal: {sig}")
    print()
