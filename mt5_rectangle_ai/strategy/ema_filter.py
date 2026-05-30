"""M15 EMA direction filter for the rectangle strategy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core.candle_builder import Candle
from strategy import skip_reasons as reasons


@dataclass(frozen=True, slots=True)
class EmaConfig:
    primary_period: int = 50
    secondary_period: int = 200
    use_secondary_confirmation: bool = False
    min_distance_from_ema_points: float = 20.0
    slope_lookback_candles: int = 5
    min_ema_slope_points: float = 5.0


@dataclass(frozen=True, slots=True)
class EmaDirection:
    direction: str | None
    ema_50: float
    ema_200: float | None
    price_vs_ema: str
    ema_slope: str
    slope_points: float
    distance_points: float
    trend_valid: bool
    skip_reason: str | None = None


def calculate_ema(values: Sequence[float], period: int) -> list[float]:
    if period <= 0:
        raise ValueError("EMA period must be positive")
    if not values:
        return []

    multiplier = 2 / (period + 1)
    ema_values = [float(values[0])]
    for value in values[1:]:
        ema_values.append((float(value) - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def evaluate_ema_direction(
    candles: Sequence[Candle],
    point: float,
    config: EmaConfig | None = None,
) -> EmaDirection:
    cfg = config or EmaConfig()
    if point <= 0:
        raise ValueError("point must be positive")
    if not candles or not candles[-1].is_closed:
        raise ValueError("EMA direction requires latest closed M15 candle")

    closes = [c.close for c in candles]
    required = max(cfg.primary_period, cfg.slope_lookback_candles + 1)
    if len(closes) < required:
        raise ValueError(f"need at least {required} closes for EMA filter")

    primary_series = calculate_ema(closes, cfg.primary_period)
    secondary_series = (
        calculate_ema(closes, cfg.secondary_period)
        if len(closes) >= cfg.secondary_period
        else []
    )

    close = closes[-1]
    ema_primary = primary_series[-1]
    ema_secondary = secondary_series[-1] if secondary_series else None
    distance_points = abs(close - ema_primary) / point
    slope_points = (ema_primary - primary_series[-1 - cfg.slope_lookback_candles]) / point
    price_vs_ema = "above" if close > ema_primary else "below" if close < ema_primary else "at"
    ema_slope = "up" if slope_points > 0 else "down" if slope_points < 0 else "flat"

    if distance_points < cfg.min_distance_from_ema_points:
        return EmaDirection(
            None,
            ema_primary,
            ema_secondary,
            price_vs_ema,
            ema_slope,
            slope_points,
            distance_points,
            False,
            reasons.SKIP_PRICE_TOO_CLOSE_TO_EMA,
        )

    if abs(slope_points) < cfg.min_ema_slope_points:
        return EmaDirection(
            None,
            ema_primary,
            ema_secondary,
            price_vs_ema,
            ema_slope,
            slope_points,
            distance_points,
            False,
            reasons.SKIP_EMA_FLAT,
        )

    direction: str | None = None
    if close > ema_primary and slope_points > cfg.min_ema_slope_points:
        direction = "long"
    elif close < ema_primary and slope_points < -cfg.min_ema_slope_points:
        direction = "short"

    if direction is None:
        return EmaDirection(
            None,
            ema_primary,
            ema_secondary,
            price_vs_ema,
            ema_slope,
            slope_points,
            distance_points,
            False,
            reasons.SKIP_NO_EMA_DIRECTION,
        )

    if cfg.use_secondary_confirmation:
        if ema_secondary is None:
            raise ValueError("secondary EMA confirmation requires more candles")
        if direction == "long" and ema_primary <= ema_secondary:
            return EmaDirection(
                None,
                ema_primary,
                ema_secondary,
                price_vs_ema,
                ema_slope,
                slope_points,
                distance_points,
                False,
                reasons.SKIP_EMA_CONFLICT,
            )
        if direction == "short" and ema_primary >= ema_secondary:
            return EmaDirection(
                None,
                ema_primary,
                ema_secondary,
                price_vs_ema,
                ema_slope,
                slope_points,
                distance_points,
                False,
                reasons.SKIP_EMA_CONFLICT,
            )

    return EmaDirection(
        direction,
        ema_primary,
        ema_secondary,
        price_vs_ema,
        ema_slope,
        slope_points,
        distance_points,
        True,
    )
