"""Fair value gap detection and level tagging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from core.candle_builder import Candle


@dataclass(frozen=True, slots=True)
class ImbalanceConfig:
    enabled: bool = True
    required: bool = False
    lookback_candles: int = 30
    buffer_points: float = 10.0


@dataclass(frozen=True, slots=True)
class FairValueGap:
    imbalance_type: Literal["bullish_fvg", "bearish_fvg"]
    low: float
    high: float
    time: object
    index: int


@dataclass(frozen=True, slots=True)
class ImbalanceTag:
    inside_imbalance: bool
    imbalance_type: str | None = None
    imbalance_low: float | None = None
    imbalance_high: float | None = None


def detect_fvgs(candles: Sequence[Candle], lookback_candles: int = 30) -> list[FairValueGap]:
    start = max(2, len(candles) - lookback_candles)
    gaps: list[FairValueGap] = []
    for index in range(start, len(candles)):
        first = candles[index - 2]
        third = candles[index]
        if first.high < third.low:
            gaps.append(FairValueGap("bullish_fvg", first.high, third.low, third.time, index))
        if first.low > third.high:
            gaps.append(FairValueGap("bearish_fvg", third.high, first.low, third.time, index))
    return gaps


def tag_level_imbalance(
    candles: Sequence[Candle],
    marked_level_price: float,
    point: float,
    config: ImbalanceConfig | None = None,
) -> ImbalanceTag:
    cfg = config or ImbalanceConfig()
    if not cfg.enabled:
        return ImbalanceTag(False)
    buffer_value = cfg.buffer_points * point
    for gap in reversed(detect_fvgs(candles, cfg.lookback_candles)):
        if gap.low - buffer_value <= marked_level_price <= gap.high + buffer_value:
            return ImbalanceTag(True, gap.imbalance_type, gap.low, gap.high)
    return ImbalanceTag(False)
