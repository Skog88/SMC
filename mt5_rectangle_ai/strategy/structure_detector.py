"""Mechanical M15 swing and continuation-structure detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from core.candle_builder import Candle
from strategy import skip_reasons as reasons


@dataclass(frozen=True, slots=True)
class StructureConfig:
    swing_left: int = 2
    swing_right: int = 2
    max_level_age_candles: int = 40


@dataclass(frozen=True, slots=True)
class SwingLevel:
    level_type: Literal["M15_LOW", "M15_HIGH"]
    price: float
    time: object
    index: int


@dataclass(frozen=True, slots=True)
class StructureResult:
    valid: bool
    direction: Literal["long", "short"]
    marked_level: SwingLevel | None
    clean_structure: bool
    skip_reason: str | None = None


def find_swing_lows(candles: Sequence[Candle], left: int = 2, right: int = 2) -> list[SwingLevel]:
    swings: list[SwingLevel] = []
    for index in range(left, len(candles) - right):
        center = candles[index]
        if all(center.low < candles[i].low for i in range(index - left, index)) and all(
            center.low < candles[i].low for i in range(index + 1, index + right + 1)
        ):
            swings.append(SwingLevel("M15_LOW", center.low, center.time, index))
    return swings


def find_swing_highs(candles: Sequence[Candle], left: int = 2, right: int = 2) -> list[SwingLevel]:
    swings: list[SwingLevel] = []
    for index in range(left, len(candles) - right):
        center = candles[index]
        if all(center.high > candles[i].high for i in range(index - left, index)) and all(
            center.high > candles[i].high for i in range(index + 1, index + right + 1)
        ):
            swings.append(SwingLevel("M15_HIGH", center.high, center.time, index))
    return swings


def level_already_swept(candles_after_level: Sequence[Candle], level: SwingLevel) -> bool:
    # Long: only a candle that closed below invalidates the level.
    # Short: only a candle that closed above invalidates the level.
    if level.level_type == "M15_LOW":
        return any(candle.close < level.price for candle in candles_after_level)
    return any(candle.close > level.price for candle in candles_after_level)


def find_continuation_level(
    candles: Sequence[Candle],
    direction: Literal["long", "short"],
    point: float,
    config: StructureConfig | None = None,
) -> StructureResult:
    cfg = config or StructureConfig()
    if point <= 0:
        raise ValueError("point must be positive")
    if len(candles) < cfg.swing_left + cfg.swing_right + 3:
        reason = reasons.SKIP_NO_VALID_SWING_LOW if direction == "long" else reasons.SKIP_NO_VALID_SWING_HIGH
        return StructureResult(False, direction, None, False, reason)

    candidates = (
        find_swing_lows(candles, cfg.swing_left, cfg.swing_right)
        if direction == "long"
        else find_swing_highs(candles, cfg.swing_left, cfg.swing_right)
    )
    if not candidates:
        reason = reasons.SKIP_NO_VALID_SWING_LOW if direction == "long" else reasons.SKIP_NO_VALID_SWING_HIGH
        return StructureResult(False, direction, None, True, reason)

    for level in reversed(candidates):
        age = len(candles) - 1 - level.index
        if age > cfg.max_level_age_candles:
            continue
        candles_after = candles[level.index + 1 : -1]
        if not level_already_swept(candles_after, level):
            return StructureResult(True, direction, level, True)

    newest = candidates[-1]
    age = len(candles) - 1 - newest.index
    if age > cfg.max_level_age_candles:
        return StructureResult(False, direction, None, True, reasons.SKIP_LEVEL_TOO_OLD)
    if level_already_swept(candles[newest.index + 1 : -1], newest):
        return StructureResult(False, direction, None, True, reasons.SKIP_LEVEL_ALREADY_SWEPT)

    reason = reasons.SKIP_NO_VALID_SWING_LOW if direction == "long" else reasons.SKIP_NO_VALID_SWING_HIGH
    return StructureResult(False, direction, None, True, reason)
