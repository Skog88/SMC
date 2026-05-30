"""Build setup and entry signal dictionaries for journaling and execution gates."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from core.candle_builder import Candle
from core.htf_engine import HTFBias
from core.sessions import KillZoneResult
from strategy.liquidity_detector import LiquidityTag
from strategy.m1_flip import M1FlipResult
from strategy.rectangle import Rectangle
from strategy.structure_detector import OrderBlock, StructureResult
from strategy.sweep_detector import SweepResult


def build_setup_id(symbol: str, trigger_time: object, direction: str) -> str:
    return f"{symbol}_{trigger_time.isoformat()}_{direction.upper()}"


def build_setup_object(
    symbol: str,
    structure: StructureResult,
    sweep: SweepResult,
    rectangle: Rectangle,
    vision_review: dict[str, Any] | None = None,
    htf_bias: HTFBias | None = None,
    ob: OrderBlock | None = None,
    ob_rectangle_overlap: bool = False,
    liq_tag: LiquidityTag | None = None,
    kz_result: KillZoneResult | None = None,
) -> dict[str, Any]:
    if structure.marked_level is None:
        raise ValueError("cannot build setup object without marked level")

    trigger = sweep.trigger_candle
    setup_id = build_setup_id(symbol, trigger.time, sweep.direction)
    return {
        "setup_id": setup_id,
        "symbol": symbol,
        "direction": sweep.direction,
        "state": "M15_WEAKNESS_CONFIRMED",
        "structure": {
            "marked_level_type": structure.marked_level.level_type,
            "marked_level_price": structure.marked_level.price,
            "level_time": structure.marked_level.time.isoformat(),
            "clean_structure": structure.clean_structure,
        },
        "sweep": {
            "trigger_time": trigger.time.isoformat(),
            "open": trigger.open,
            "high": trigger.high,
            "low": trigger.low,
            "close": trigger.close,
            "sweep_depth_points": sweep.sweep_depth_points,
            "wick_size_points": sweep.wick_size_points,
            "close_position": sweep.close_position,
            "valid_weakness": sweep.valid_weakness,
        },
        "rectangle": {
            "low": rectangle.low,
            "high": rectangle.high,
            "size_points": rectangle.size_points,
        },
        "vision_review": vision_review or {},
        "htf_bias": {
            "bias": htf_bias.bias if htf_bias else None,
            "last_bos_level": htf_bias.last_bos_level if htf_bias else None,
            "last_bos_time": htf_bias.last_bos_time.isoformat() if htf_bias and htf_bias.last_bos_time else None,
            "last_swing_high": htf_bias.last_swing_high if htf_bias else None,
            "last_swing_low": htf_bias.last_swing_low if htf_bias else None,
            "swing_midpoint": htf_bias.swing_midpoint if htf_bias else None,
        },
        "order_block": {
            "ob_high": ob.ob_high if ob else None,
            "ob_low": ob.ob_low if ob else None,
            "ob_origin_time": ob.ob_origin_time.isoformat() if ob and ob.ob_origin_time else None,
            "ob_timeframe": ob.ob_timeframe if ob else None,
            "ob_mitigation_count": ob.ob_mitigation_count if ob else None,
            "ob_fvg_overlap": ob.ob_fvg_overlap if ob else False,
            "ob_valid": ob.ob_valid if ob else False,
            "ob_rectangle_overlap": ob_rectangle_overlap,
        },
        "liquidity": {
            "swept_level_type": liq_tag.swept_level_type if liq_tag else "single_swing",
            "liquidity_pool_touches": liq_tag.liquidity_pool_touches if liq_tag else 1,
        },
        "kill_zone": {
            "in_kill_zone": kz_result.in_kill_zone if kz_result else False,
            "kill_zone_name": kz_result.kill_zone_name if kz_result else "none",
        },
        "status": "RECTANGLE_ACTIVE",
    }


def build_ai_request(setup: dict[str, Any]) -> dict[str, Any]:
    return {
        "setup_id": setup["setup_id"],
        "symbol": setup["symbol"],
        "timeframe": "M15",
        "direction": setup["direction"],
        "structure": setup["structure"],
        "sweep": setup["sweep"],
        "rectangle": setup["rectangle"],
    }


def build_entry_signal(
    setup: dict[str, Any],
    flip: M1FlipResult,
    rectangle: Rectangle,
    entry_price: float,
    sl: float,
    tp: float,
    planned_rr: float,
) -> dict[str, Any]:
    if flip.trigger_candle is None or flip.direction is None:
        raise ValueError("cannot build entry signal without confirmed M1 flip")

    return {
        "setup_id": setup["setup_id"],
        "symbol": setup["symbol"],
        "direction": flip.direction,
        "entry_reason": flip.entry_reason,
        "m1_trigger_time": flip.trigger_candle.time.isoformat(),
        "m1_close": flip.trigger_candle.close,
        "rectangle_high": rectangle.high,
        "rectangle_low": rectangle.low,
        "entry_price": entry_price,
        "sl": sl,
        "tp": tp,
        "planned_rr": planned_rr,
        "status": "READY_FOR_RISK_CHECK",
    }


def dataclass_to_dict(value: object) -> dict[str, Any]:
    return asdict(value)
