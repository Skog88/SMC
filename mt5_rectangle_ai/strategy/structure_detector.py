"""Mechanical M15 swing, continuation-structure, and Order Block detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True, slots=True)
class OrderBlockConfig:
    max_lookback_candles: int = 20
    require_ob: bool = True
    require_unmitigated: bool = True
    max_mitigation_count: int = 1
    min_ob_size_points: float = 5.0


@dataclass(frozen=True, slots=True)
class OrderBlock:
    ob_high: float
    ob_low: float
    ob_origin_time: datetime | None
    ob_timeframe: str
    ob_mitigation_count: int
    ob_fvg_overlap: bool
    ob_valid: bool
    skip_reason: str | None = None


def _has_fvg_overlap(candles: Sequence[Candle], ob_high: float, ob_low: float) -> bool:
    """Return True if any FVG in the candle window overlaps the OB zone."""
    for i in range(2, len(candles)):
        first, third = candles[i - 2], candles[i]
        # Bullish FVG: gap between first.high and third.low
        if first.high < third.low:
            fvg_low, fvg_high = first.high, third.low
            if fvg_low < ob_high and fvg_high > ob_low:
                return True
        # Bearish FVG: gap between third.high and first.low
        if first.low > third.high:
            fvg_low, fvg_high = third.high, first.low
            if fvg_low < ob_high and fvg_high > ob_low:
                return True
    return False


def identify_order_block(
    candles: Sequence[Candle],
    direction: Literal["long", "short"],
    point: float,
    config: OrderBlockConfig | None = None,
) -> OrderBlock:
    """Find the last opposing candle before the sweep impulse.

    For long: last bearish candle (close < open) before the sweep.
    For short: last bullish candle (close > open) before the sweep.
    The mitigation count is how many subsequent candles entered the OB zone.
    """
    cfg = config or OrderBlockConfig()

    # Lookback: candles before the sweep candle (which is candles[-1])
    lookback_start = max(0, len(candles) - 1 - cfg.max_lookback_candles)
    lookback = list(candles[lookback_start: len(candles) - 1])

    ob_candle = None
    ob_abs_index = -1

    for i in range(len(lookback) - 1, -1, -1):
        c = lookback[i]
        is_opposing = (c.close < c.open) if direction == "long" else (c.close > c.open)
        if is_opposing:
            ob_candle = c
            ob_abs_index = lookback_start + i
            break

    if ob_candle is None:
        return OrderBlock(0.0, 0.0, None, "M15", 0, False, False, reasons.SKIP_NO_ORDER_BLOCK_FOUND)

    ob_high = max(ob_candle.open, ob_candle.close)
    ob_low = min(ob_candle.open, ob_candle.close)

    ob_size_pts = (ob_high - ob_low) / point
    if ob_size_pts < cfg.min_ob_size_points:
        # Too small — search one more candle back for a larger one
        for i in range(ob_abs_index - lookback_start - 1, -1, -1):
            c = lookback[i]
            is_opposing = (c.close < c.open) if direction == "long" else (c.close > c.open)
            if is_opposing and (max(c.open, c.close) - min(c.open, c.close)) / point >= cfg.min_ob_size_points:
                ob_candle = c
                ob_abs_index = lookback_start + i
                ob_high = max(ob_candle.open, ob_candle.close)
                ob_low = min(ob_candle.open, ob_candle.close)
                break

    # Mitigation: candles between OB and sweep that entered the OB zone
    candles_after_ob = candles[ob_abs_index + 1: len(candles) - 1]
    mitigation_count = sum(
        1 for c in candles_after_ob if c.low <= ob_high and c.high >= ob_low
    )

    if cfg.require_unmitigated and mitigation_count > cfg.max_mitigation_count:
        return OrderBlock(
            ob_high, ob_low, ob_candle.time, "M15",
            mitigation_count, False, False, reasons.SKIP_OB_FULLY_MITIGATED,
        )

    # FVG overlap: any gap in the candles after the OB that intersects the OB zone
    fvg_overlap = _has_fvg_overlap(candles[ob_abs_index:], ob_high, ob_low)

    return OrderBlock(
        ob_high=ob_high,
        ob_low=ob_low,
        ob_origin_time=ob_candle.time,
        ob_timeframe="M15",
        ob_mitigation_count=mitigation_count,
        ob_fvg_overlap=fvg_overlap,
        ob_valid=True,
        skip_reason=None,
    )


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
