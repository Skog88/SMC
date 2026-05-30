"""Shared candle model and normalization helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    timeframe: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int = 0
    spread: float = 0.0
    is_closed: bool = True

    @property
    def range(self) -> float:
        return self.high - self.low

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["time"] = self.time.isoformat()
        return data


def normalize_candle(raw: Mapping[str, Any], symbol: str, timeframe: str) -> Candle:
    """Convert MT5-like dictionaries into the standard candle object."""
    value_time = raw.get("time")
    if isinstance(value_time, datetime):
        candle_time = value_time
    elif isinstance(value_time, (int, float)):
        candle_time = datetime.fromtimestamp(value_time)
    elif isinstance(value_time, str):
        candle_time = datetime.fromisoformat(value_time)
    else:
        raise ValueError("raw candle is missing a usable time value")

    return Candle(
        symbol=str(raw.get("symbol", symbol)),
        timeframe=str(raw.get("timeframe", timeframe)),
        time=candle_time,
        open=float(raw["open"]),
        high=float(raw["high"]),
        low=float(raw["low"]),
        close=float(raw["close"]),
        tick_volume=int(raw.get("tick_volume", raw.get("real_volume", 0))),
        spread=float(raw.get("spread", 0.0)),
        is_closed=bool(raw.get("is_closed", True)),
    )


def require_closed(candle: Candle) -> None:
    if not candle.is_closed:
        raise ValueError(f"{candle.symbol} {candle.timeframe} candle is not closed")
