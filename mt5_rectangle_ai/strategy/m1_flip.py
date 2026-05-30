"""M1 close-outside-rectangle entry confirmation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from core.candle_builder import Candle
from strategy import skip_reasons as reasons
from strategy.rectangle import Rectangle


@dataclass(frozen=True, slots=True)
class M1FlipConfig:
    require_closed_candle: bool = True
    max_wait_candles: int = 0
    flip_buffer_points: float = 0.0
    entry_mode: str = "market_after_close"


@dataclass(frozen=True, slots=True)
class M1FlipResult:
    confirmed: bool
    direction: Literal["buy", "sell"] | None
    trigger_candle: Candle | None
    entry_reason: str | None
    skip_reason: str | None = None


def detect_m1_flip(
    m1_candles_after_rectangle: Sequence[Candle],
    rectangle: Rectangle,
    point: float,
    config: M1FlipConfig | None = None,
) -> M1FlipResult:
    cfg = config or M1FlipConfig()
    if point <= 0:
        raise ValueError("point must be positive")

    watched = (
        list(m1_candles_after_rectangle)
        if cfg.max_wait_candles == 0
        else list(m1_candles_after_rectangle[: cfg.max_wait_candles])
    )
    buffer_value = cfg.flip_buffer_points * point
    for candle in watched:
        if cfg.require_closed_candle and not candle.is_closed:
            continue
        if rectangle.direction == "long" and candle.close > rectangle.high + buffer_value:
            return M1FlipResult(True, "buy", candle, "M1_CLOSE_ABOVE_RECTANGLE")
        if rectangle.direction == "short" and candle.close < rectangle.low - buffer_value:
            return M1FlipResult(True, "sell", candle, "M1_CLOSE_BELOW_RECTANGLE")

    if cfg.max_wait_candles > 0 and len(m1_candles_after_rectangle) >= cfg.max_wait_candles:
        return M1FlipResult(False, None, None, None, reasons.SKIP_M1_FLIP_TIMEOUT)
    return M1FlipResult(False, None, None, None, reasons.SKIP_M1_CLOSE_NOT_OUTSIDE_RECTANGLE)
