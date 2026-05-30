"""Liquidity pool detection — classify swept levels as single swing, double/triple
top/bottom, or session high/low."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from core.candle_builder import Candle
from strategy.session_levels import SessionConfig, tag_session_level
from strategy.structure_detector import find_swing_highs, find_swing_lows


SweptLevelType = Literal[
    "single_swing",
    "double_top", "double_bottom",
    "triple_top", "triple_bottom",
    "session_high", "session_low",
]


@dataclass(frozen=True, slots=True)
class LiquidityConfig:
    equal_level_buffer_points: float = 5.0   # resolved per symbol in config_loader
    min_touches: int = 2
    lookback_candles: int = 60
    swing_left: int = 2
    swing_right: int = 2


@dataclass(frozen=True, slots=True)
class LiquidityTag:
    swept_level_type: SweptLevelType
    liquidity_pool_touches: int


def _count_equal_swings(
    candles: Sequence[Candle],
    level_price: float,
    direction: Literal["long", "short"],
    buffer_value: float,
    left: int,
    right: int,
) -> int:
    """Count confirmed swing points within buffer_value of level_price."""
    if direction == "long":
        swings = find_swing_lows(candles, left, right)
        count = sum(1 for s in swings if abs(s.price - level_price) <= buffer_value)
    else:
        swings = find_swing_highs(candles, left, right)
        count = sum(1 for s in swings if abs(s.price - level_price) <= buffer_value)
    return max(count, 1)  # the swept level itself counts as at least 1


def classify_swept_level(
    candles: Sequence[Candle],
    swept_level_price: float,
    direction: Literal["long", "short"],
    point: float,
    config: LiquidityConfig | None = None,
    session_config: SessionConfig | None = None,
) -> LiquidityTag:
    """Classify the swept level as a single swing, pool, or session level.

    Priority: session_high/low > triple > double > single_swing.
    session wins even if the touch count is 1 — session extremes are always
    high-probability targets regardless of equal-level count.
    """
    cfg = config or LiquidityConfig()
    buffer_value = cfg.equal_level_buffer_points * point

    # Slice lookback window (exclude the sweep candle itself)
    lookback = list(candles[-(cfg.lookback_candles + 1): -1])

    # ── Equal-level count ───────────────────────────────────────────────────
    touches = _count_equal_swings(lookback, swept_level_price, direction, buffer_value, cfg.swing_left, cfg.swing_right)

    if direction == "long":
        if touches >= 3:
            base_type: SweptLevelType = "triple_bottom"
        elif touches >= 2:
            base_type = "double_bottom"
        else:
            base_type = "single_swing"
    else:
        if touches >= 3:
            base_type = "triple_top"
        elif touches >= 2:
            base_type = "double_top"
        else:
            base_type = "single_swing"

    # ── Session level check (overrides base type) ───────────────────────────
    session_tag = tag_session_level(lookback, swept_level_price, point, session_config)
    if session_tag.level_is_session_high_low:
        final_type: SweptLevelType = (
            "session_high" if direction == "short" else "session_low"
        )
        return LiquidityTag(swept_level_type=final_type, liquidity_pool_touches=touches)

    return LiquidityTag(swept_level_type=base_type, liquidity_pool_touches=touches)
