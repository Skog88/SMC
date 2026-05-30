"""Rectangle creation and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.candle_builder import Candle
from strategy import skip_reasons as reasons


@dataclass(frozen=True, slots=True)
class RectangleConfig:
    min_size_points: float = 5.0
    max_size_points: float = 200.0
    expires_after_m1_candles: int = 30


@dataclass(frozen=True, slots=True)
class Rectangle:
    direction: Literal["long", "short"]
    low: float
    high: float
    size_points: float
    trigger_time: object
    valid: bool
    skip_reason: str | None = None


def build_rectangle(
    trigger_candle: Candle,
    direction: Literal["long", "short"],
    point: float,
    config: RectangleConfig | None = None,
) -> Rectangle:
    cfg = config or RectangleConfig()
    if point <= 0:
        raise ValueError("point must be positive")

    if direction == "long":
        low = trigger_candle.low
        high = trigger_candle.close
    else:
        low = trigger_candle.close
        high = trigger_candle.high

    size_points = (high - low) / point
    reason = None
    if size_points < cfg.min_size_points:
        reason = reasons.SKIP_RECTANGLE_TOO_SMALL
    elif size_points > cfg.max_size_points:
        reason = reasons.SKIP_RECTANGLE_TOO_LARGE

    return Rectangle(direction, low, high, size_points, trigger_candle.time, reason is None, reason)
