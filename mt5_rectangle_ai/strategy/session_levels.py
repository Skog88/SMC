"""Session high/low tagging for marked M15 levels."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Mapping, Sequence

from core.candle_builder import Candle


@dataclass(frozen=True, slots=True)
class SessionWindow:
    name: str
    start: time
    end: time


@dataclass(frozen=True, slots=True)
class SessionConfig:
    enabled: bool = True
    required: bool = False
    buffer_points: float = 10.0
    windows: tuple[SessionWindow, ...] = (
        SessionWindow("Asia", time(0, 0), time(8, 0)),
        SessionWindow("London", time(8, 0), time(17, 0)),
        SessionWindow("New York", time(14, 30), time(22, 0)),
    )


@dataclass(frozen=True, slots=True)
class SessionLevelTag:
    session: str | None
    level_is_session_high_low: bool
    related_session_level: str | None = None


def parse_session_config(raw: Mapping[str, object] | None) -> SessionConfig:
    if raw is None:
        return SessionConfig()

    def parse_clock(value: str) -> time:
        hour, minute = value.split(":", 1)
        return time(int(hour), int(minute))

    windows: list[SessionWindow] = []
    for name in ("asia", "london", "new_york"):
        item = raw.get(name)
        if isinstance(item, Mapping):
            display = "New York" if name == "new_york" else name.title()
            windows.append(SessionWindow(display, parse_clock(str(item["start"])), parse_clock(str(item["end"]))))
    return SessionConfig(windows=tuple(windows) or SessionConfig().windows)


def _in_window(value: time, window: SessionWindow) -> bool:
    if window.start <= window.end:
        return window.start <= value < window.end
    return value >= window.start or value < window.end


def tag_session_level(
    candles: Sequence[Candle],
    marked_level_price: float,
    point: float,
    config: SessionConfig | None = None,
) -> SessionLevelTag:
    cfg = config or SessionConfig()
    if not cfg.enabled:
        return SessionLevelTag(None, False)
    buffer_value = cfg.buffer_points * point
    for window in cfg.windows:
        session_candles = [candle for candle in candles if _in_window(candle.time.timetz().replace(tzinfo=None), window)]
        if not session_candles:
            continue
        high = max(candle.high for candle in session_candles)
        low = min(candle.low for candle in session_candles)
        if abs(marked_level_price - high) <= buffer_value:
            return SessionLevelTag(window.name, True, f"{window.name} high")
        if abs(marked_level_price - low) <= buffer_value:
            return SessionLevelTag(window.name, True, f"{window.name} low")
    return SessionLevelTag(None, False)
