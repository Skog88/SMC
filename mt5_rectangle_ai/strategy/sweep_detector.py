"""M15 weakness sweep detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.candle_builder import Candle
from strategy import skip_reasons as reasons
from strategy.structure_detector import SwingLevel


@dataclass(frozen=True, slots=True)
class SweepConfig:
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class SweepResult:
    valid: bool
    direction: Literal["long", "short"]
    trigger_candle: Candle
    sweep_depth_points: float
    wick_size_points: float
    close_position: float
    valid_weakness: bool
    skip_reason: str | None = None


def detect_weakness_sweep(
    trigger_candle: Candle,
    marked_level: SwingLevel,
    direction: Literal["long", "short"],
    point: float,
    config: SweepConfig | None = None,
) -> SweepResult:
    cfg = config or SweepConfig()
    if point <= 0:
        raise ValueError("point must be positive")
    if not trigger_candle.is_closed:
        raise ValueError("weakness sweep requires a closed M15 candle")

    if direction == "long":
        swept = trigger_candle.low < marked_level.price
        closed_back = trigger_candle.close > marked_level.price
        correct_colour = trigger_candle.close < trigger_candle.open
        sweep_depth_points = (marked_level.price - trigger_candle.low) / point if swept else 0.0
        wick_size_points = (min(trigger_candle.open, trigger_candle.close) - trigger_candle.low) / point
    else:
        swept = trigger_candle.high > marked_level.price
        closed_back = trigger_candle.close < marked_level.price
        correct_colour = trigger_candle.close > trigger_candle.open
        sweep_depth_points = (trigger_candle.high - marked_level.price) / point if swept else 0.0
        wick_size_points = (trigger_candle.high - max(trigger_candle.open, trigger_candle.close)) / point

    candle_range = trigger_candle.high - trigger_candle.low
    close_position = 0.5 if candle_range <= 0 else (trigger_candle.close - trigger_candle.low) / candle_range

    if not swept:
        reason = reasons.SKIP_NO_SWEEP
    elif not closed_back:
        reason = reasons.SKIP_SWEEP_CLOSED_BEYOND_LEVEL
    elif not correct_colour:
        reason = reasons.SKIP_WRONG_CANDLE_COLOUR
    else:
        reason = None

    return SweepResult(
        reason is None,
        direction,
        trigger_candle,
        sweep_depth_points,
        wick_size_points,
        close_position,
        reason is None,
        reason,
    )
