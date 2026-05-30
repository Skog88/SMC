"""Fetch and cache historical candle data from MT5 for offline backtesting.

Run once (or whenever you want fresh data):
    python backtesting/fetch_historical.py --symbols EURUSD NAS100 --days 90

Then pass --data-dir to mechanical_backtest.py to skip live MT5 calls:
    python backtesting/mechanical_backtest.py --symbol EURUSD --days 30 \\
        --data-dir C:\\15m-1m\\data\\historical

Data is saved per symbol:
    data/historical/
    ├── EURUSD/
    │   ├── M15.csv
    │   ├── M1.csv
    │   └── symbol_info.json
    └── NAS100/
        ├── M15.csv
        ├── M1.csv
        └── symbol_info.json
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from core.data_engine import Mt5DataEngine
from core.mt5_mcp_client import Mt5McpClient, Mt5McpConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "historical"

CANDLE_FIELDS = ["symbol", "timeframe", "time", "open", "high", "low", "close", "tick_volume", "spread"]

# Rough bar counts per timeframe per day (24/5 markets, worst case)
_H4_PER_DAY  = 24 // 4   # 6
_M15_PER_DAY = 24 * 4    # 96
_M1_PER_DAY  = 24 * 60   # 1440


def fetch_symbol(symbol: str, days: int, data_dir: Path) -> None:
    # Use a generous count so we always have enough warmup bars
    engine = Mt5DataEngine(client=Mt5McpClient(Mt5McpConfig(
        server_script=Path("C:/mt5-mcp/mt5_mcp_server.py"),
    )))

    sym_dir = data_dir / symbol
    sym_dir.mkdir(parents=True, exist_ok=True)

    # ── symbol_info ───────────────────────────────────────────────────────
    print(f"[{symbol}] Fetching symbol_info...", flush=True)
    info = engine.symbol_info(symbol)
    info_path = sym_dir / "symbol_info.json"
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"[{symbol}] symbol_info -> {info_path}")

    # ── candles ───────────────────────────────────────────────────────────
    specs = [
        ("H4",  days * _H4_PER_DAY  + 200),
        ("M15", days * _M15_PER_DAY + 1000),
        ("M1",  days * _M1_PER_DAY  + 5000),
    ]
    for tf, total_count in specs:
        t0 = datetime.now()

        # MT5 copy_rates_from_pos rejects requests above ~65 000 bars.
        # Fetch in chunks starting from pos=0 (most recent) and stepping back.
        CHUNK = 50_000
        chunks: list[list] = []
        pos = 0
        remaining = total_count
        print(f"[{symbol}] Fetching {total_count:,} {tf} bars in chunks of {CHUNK:,}...", flush=True)
        while remaining > 0:
            fetch_n = min(CHUNK, remaining)
            try:
                raw = engine.client.call_tool(
                    "get_candles",
                    {"symbol": symbol, "timeframe": tf, "count": fetch_n, "pos": pos},
                )
            except Exception as exc:
                safe_msg = str(exc).encode("ascii", errors="replace").decode("ascii")
                print(f"[{symbol}]   MT5 history exhausted at pos={pos}: {safe_msg}", flush=True)
                break
            batch = raw.get("candles", []) if isinstance(raw, dict) else []
            if not batch:
                break
            chunks.append(batch)
            pos += len(batch)
            remaining -= len(batch)
            print(f"[{symbol}]   chunk pos={pos - len(batch):,}  got {len(batch):,} bars", flush=True)
            if len(batch) < fetch_n:
                break  # broker ran out of history

        # Merge chunks (oldest first — each chunk is oldest→newest)
        all_raw = []
        for chunk in reversed(chunks):
            all_raw.extend(chunk)

        # Deduplicate by time (overlap possible at chunk boundaries)
        seen: set[str] = set()
        unique_raw = []
        for r in all_raw:
            if r["time"] not in seen:
                seen.add(r["time"])
                unique_raw.append(r)
        unique_raw.sort(key=lambda r: r["time"])

        elapsed = (datetime.now() - t0).total_seconds()
        path = sym_dir / f"{tf}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(CANDLE_FIELDS)
            for r in unique_raw:
                writer.writerow([
                    symbol, tf, r["time"],
                    r["open"], r["high"], r["low"], r["close"],
                    r.get("volume", 0), 0,
                ])

        first = unique_raw[0]["time"] if unique_raw else "n/a"
        last  = unique_raw[-1]["time"] if unique_raw else "n/a"
        print(
            f"[{symbol}] {len(unique_raw):,} {tf} bars saved in {elapsed:.1f}s "
            f"({first} to {last}) -> {path}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and cache historical MT5 candle data.")
    parser.add_argument("--symbols", nargs="+", default=["EURUSD", "NAS100"],
                        help="Symbols to fetch (space-separated).")
    parser.add_argument("--days", type=int, default=90,
                        help="Number of days of history to fetch.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR),
                        help="Directory to write data into.")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    print(f"Output directory : {data_dir}")
    print(f"Symbols          : {args.symbols}")
    print(f"Days             : {args.days}")
    print()

    for symbol in args.symbols:
        fetch_symbol(symbol.upper(), args.days, data_dir)
        print()

    print("All done.")


if __name__ == "__main__":
    main()
