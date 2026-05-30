"""HTF (H4) bias engine — BOS detection, directional bias, premium/discount zones."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Sequence

from core.candle_builder import Candle


@dataclass(frozen=True, slots=True)
class HTFConfig:
    timeframe: str = "H4"
    swing_left: int = 3
    swing_right: int = 3
    max_bos_age_candles: int = 50
    require_confirmed_bos: bool = True


@dataclass(frozen=True, slots=True)
class HTFBias:
    bias: Literal["bullish", "bearish", "neutral"]
    last_bos_level: float | None
    last_bos_time: datetime | None
    last_swing_high: float | None
    last_swing_low: float | None
    swing_midpoint: float | None


def _swing_highs(candles: Sequence[Candle], left: int, right: int) -> list[tuple[int, float, datetime]]:
    result = []
    for i in range(left, len(candles) - right):
        c = candles[i]
        if (
            all(c.high > candles[j].high for j in range(i - left, i))
            and all(c.high > candles[j].high for j in range(i + 1, i + right + 1))
        ):
            result.append((i, c.high, c.time))
    return result


def _swing_lows(candles: Sequence[Candle], left: int, right: int) -> list[tuple[int, float, datetime]]:
    result = []
    for i in range(left, len(candles) - right):
        c = candles[i]
        if (
            all(c.low < candles[j].low for j in range(i - left, i))
            and all(c.low < candles[j].low for j in range(i + 1, i + right + 1))
        ):
            result.append((i, c.low, c.time))
    return result


def detect_htf_bias(candles: Sequence[Candle], config: HTFConfig | None = None) -> HTFBias:
    """Detect the most recent confirmed H4 BOS and return directional bias.

    Returns neutral when there are insufficient candles or no BOS found within
    max_bos_age_candles.
    """
    cfg = config or HTFConfig()
    min_len = cfg.swing_left + cfg.swing_right + 2
    if len(candles) < min_len:
        return HTFBias("neutral", None, None, None, None, None)

    highs = _swing_highs(candles, cfg.swing_left, cfg.swing_right)
    lows = _swing_lows(candles, cfg.swing_left, cfg.swing_right)

    if not highs or not lows:
        return HTFBias("neutral", None, None, None, None, None)

    last_sh_price = highs[-1][1]
    last_sl_price = lows[-1][1]
    midpoint = (last_sh_price + last_sl_price) / 2

    last_bos_index = -1
    last_bos_bias: Literal["bullish", "bearish", "neutral"] = "neutral"
    last_bos_level: float | None = None
    last_bos_time: datetime | None = None

    # Bullish BOS: a candle closed above a prior confirmed swing high
    for sh_idx, sh_price, _ in highs:
        earliest = max(sh_idx + 1, len(candles) - cfg.max_bos_age_candles)
        for i in range(earliest, len(candles)):
            if candles[i].close > sh_price:
                if i > last_bos_index:
                    last_bos_index = i
                    last_bos_bias = "bullish"
                    last_bos_level = sh_price
                    last_bos_time = candles[i].time
                break

    # Bearish BOS: a candle closed below a prior confirmed swing low
    for sl_idx, sl_price, _ in lows:
        earliest = max(sl_idx + 1, len(candles) - cfg.max_bos_age_candles)
        for i in range(earliest, len(candles)):
            if candles[i].close < sl_price:
                if i > last_bos_index:
                    last_bos_index = i
                    last_bos_bias = "bearish"
                    last_bos_level = sl_price
                    last_bos_time = candles[i].time
                break

    if last_bos_bias == "neutral":
        return HTFBias("neutral", None, None, last_sh_price, last_sl_price, midpoint)

    return HTFBias(
        bias=last_bos_bias,
        last_bos_level=last_bos_level,
        last_bos_time=last_bos_time,
        last_swing_high=last_sh_price,
        last_swing_low=last_sl_price,
        swing_midpoint=midpoint,
    )


# ── Premium / Discount zone ───────────────────────────────────────────────────

ZoneType = Literal["premium", "discount", "equilibrium"]


@dataclass(frozen=True, slots=True)
class PremiumDiscountConfig:
    enabled: bool = True
    hard_filter: bool = False
    equilibrium_buffer_pct: float = 5.0


@dataclass(frozen=True, slots=True)
class PremiumDiscountResult:
    zone_type: ZoneType
    distance_from_midpoint_pct: float


def get_premium_discount_zone(
    current_price: float,
    htf_bias: HTFBias,
    config: PremiumDiscountConfig | None = None,
) -> PremiumDiscountResult:
    """Classify current_price relative to the H4 swing range midpoint.

    equilibrium_buffer_pct is applied as a fraction of the total swing range.
    distance_from_midpoint_pct is positive in premium, negative in discount.
    Returns equilibrium when HTF swing data is unavailable.
    """
    cfg = config or PremiumDiscountConfig()

    if (
        not cfg.enabled
        or htf_bias.swing_midpoint is None
        or htf_bias.last_swing_high is None
        or htf_bias.last_swing_low is None
    ):
        return PremiumDiscountResult("equilibrium", 0.0)

    midpoint   = htf_bias.swing_midpoint
    range_size = htf_bias.last_swing_high - htf_bias.last_swing_low

    if range_size <= 0:
        return PremiumDiscountResult("equilibrium", 0.0)

    equi_buffer = range_size * (cfg.equilibrium_buffer_pct / 100.0)
    distance    = current_price - midpoint
    distance_pct = distance / range_size * 100.0

    if current_price > midpoint + equi_buffer:
        zone: ZoneType = "premium"
    elif current_price < midpoint - equi_buffer:
        zone = "discount"
    else:
        zone = "equilibrium"

    return PremiumDiscountResult(zone_type=zone, distance_from_midpoint_pct=round(distance_pct, 4))
