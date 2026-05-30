"""Load cached candle data from disk — drop-in replacement for Mt5DataEngine.

Used by mechanical_backtest.py when --data-dir is supplied.  Reads CSV files
written by backtesting/fetch_historical.py.  Has the same interface as
Mt5DataEngine so the backtest code needs no special-casing.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.candle_builder import Candle


class LocalDataEngine:
    """Reads candle data from pre-fetched CSV files instead of calling MT5."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)

    # ── public interface (mirrors Mt5DataEngine) ──────────────────────────

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int,
        drop_current: bool = True,
    ) -> list[Candle]:
        """Return all cached candles for symbol/timeframe.

        The `count` parameter is intentionally ignored: the backtest already
        filters by start_time/end_time, so returning the full dataset is both
        correct and allows any sub-window to be tested without re-fetching.
        """
        path = self.data_dir / symbol / f"{timeframe}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"No cached data at {path}.\n"
                f"Run:  python backtesting/fetch_historical.py --symbols {symbol}"
            )
        candles: list[Candle] = []
        with path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                candles.append(Candle(
                    symbol=row["symbol"],
                    timeframe=row["timeframe"],
                    time=datetime.fromisoformat(row["time"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    tick_volume=int(row["tick_volume"]),
                    spread=float(row["spread"]),
                    is_closed=True,
                ))
        if drop_current and candles:
            candles = candles[:-1]
        return candles

    def symbol_info(self, symbol: str) -> dict[str, Any]:
        path = self.data_dir / symbol / "symbol_info.json"
        if not path.exists():
            raise FileNotFoundError(
                f"No symbol_info at {path}.\n"
                f"Run:  python backtesting/fetch_historical.py --symbols {symbol}"
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def account_info(self) -> dict[str, Any]:
        raise NotImplementedError(
            "account_info is not available in local (cached) mode."
        )

    # ── helpers used by Mt5DataEngine that callers might reference ────────

    def latest_closed_m15(self, symbol: str, count: int) -> list[Candle]:
        return self.get_candles(symbol, "M15", count, drop_current=True)

    def m1_after(self, symbol: str, start_time: object, max_count: int) -> list[Candle]:
        candles = self.get_candles(symbol, "M1", max_count, drop_current=True)
        if not isinstance(start_time, datetime):
            return candles[:max_count]
        return [c for c in candles if c.time > start_time][:max_count]
