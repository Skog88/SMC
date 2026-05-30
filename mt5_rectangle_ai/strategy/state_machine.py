"""Per-symbol deterministic rule-engine flow."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Sequence

from ai.vision_client import ask_claude_vision
from core.candle_builder import Candle
from core.chart_renderer import render_sweep_chart
from core.htf_engine import HTFBias, HTFConfig, detect_htf_bias
from strategy import skip_reasons as reasons
from strategy.m1_flip import M1FlipConfig, detect_m1_flip
from strategy.rectangle import RectangleConfig, build_rectangle
from strategy.signal_builder import build_entry_signal, build_setup_object
from strategy.structure_detector import (
    OrderBlock, OrderBlockConfig, StructureConfig,
    find_continuation_level, identify_order_block,
)
from strategy.sweep_detector import SweepConfig, detect_weakness_sweep


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class RuleEngineConfig:
    structure: StructureConfig = field(default_factory=StructureConfig)
    sweep: SweepConfig = field(default_factory=SweepConfig)
    rectangle: RectangleConfig = field(default_factory=RectangleConfig)
    m1_flip: M1FlipConfig = field(default_factory=M1FlipConfig)
    htf_config: HTFConfig = field(default_factory=HTFConfig)
    ob_config: OrderBlockConfig = field(default_factory=OrderBlockConfig)
    ai_model: str = "claude-sonnet-4-6"
    ai_min_confidence: int = 60
    sl_buffer_points: float = 5.0
    planned_rr: float = 3.0


@dataclass(frozen=True, slots=True)
class RuleDecision:
    decision: str
    setup: dict[str, Any] | None = None
    entry_signal: dict[str, Any] | None = None
    skip_reason: str | None = None


class SymbolRuleState:
    """Owns one symbol's mechanical setup lifecycle."""

    def __init__(self, symbol: str, point: float, config: RuleEngineConfig | None = None) -> None:
        if point <= 0:
            raise ValueError("point must be positive")
        self.symbol = symbol
        self.point = point
        self.config = config or RuleEngineConfig()
        self.state = "IDLE"
        self.active_setup: dict[str, Any] | None = None
        self.active_rectangle = None

    def scan_m15(
        self,
        m15_candles: Sequence[Candle],
        h4_candles: Sequence[Candle] | None = None,
        use_vision: bool = True,
    ) -> RuleDecision:
        """Find a three-check sweep, gate it with vision when enabled, then activate the rectangle.

        h4_candles: closed H4 bars up to (not including) the current M15 bar's time.
        When provided, an HTF BOS bias check runs as the first gate.
        """
        if not m15_candles:
            return RuleDecision(reasons.NO_SETUP, skip_reason=reasons.SKIP_NO_SWEEP)
        trigger = m15_candles[-1]
        if not trigger.is_closed:
            raise ValueError("latest M15 candle must be closed")

        # ── HTF bias gate (Phase 1) ───────────────────────────────────────────
        htf_bias: HTFBias | None = None
        if h4_candles:
            htf_bias = detect_htf_bias(h4_candles, self.config.htf_config)
            if htf_bias.bias == "neutral":
                self.state = "HTF_BIAS_NEUTRAL"
                return RuleDecision(reasons.NO_SETUP, skip_reason=reasons.SKIP_HTF_BIAS_NEUTRAL)

        last_skip: str | None = None
        for direction in ("long", "short"):
            # HTF bias conflict check: skip directions that oppose the H4 bias
            if htf_bias is not None:
                if htf_bias.bias == "bullish" and direction == "short":
                    last_skip = reasons.SKIP_HTF_BIAS_CONFLICT
                    continue
                if htf_bias.bias == "bearish" and direction == "long":
                    last_skip = reasons.SKIP_HTF_BIAS_CONFLICT
                    continue

            structure = find_continuation_level(m15_candles, direction, self.point, self.config.structure)
            if not structure.valid or structure.marked_level is None:
                last_skip = structure.skip_reason
                continue

            sweep = detect_weakness_sweep(trigger, structure.marked_level, direction, self.point, self.config.sweep)
            if not sweep.valid:
                last_skip = sweep.skip_reason
                continue

            # ── Order Block check (Phase 2) ───────────────────────────────────
            ob = identify_order_block(m15_candles, direction, self.point, self.config.ob_config)
            if not ob.ob_valid:
                if self.config.ob_config.require_ob:
                    last_skip = ob.skip_reason
                    continue
            # OB is always logged even if filter is off

            rectangle = build_rectangle(trigger, direction, self.point, self.config.rectangle)
            if not rectangle.valid:
                return RuleDecision(reasons.NO_SETUP, skip_reason=rectangle.skip_reason)

            # OB–rectangle overlap (confluence signal, not a hard filter)
            ob_rectangle_overlap = (
                ob.ob_valid
                and ob.ob_high > rectangle.low
                and ob.ob_low < rectangle.high
            )

            vision_review = {"approved": True, "confidence": 100, "reason": "auto_approved"}
            if use_vision:
                image_path = self._render_sweep_chart(m15_candles, trigger, structure.marked_level.price, rectangle, direction)
                vision_review = ask_claude_vision(image_path, direction, self.symbol)
                if (
                    not vision_review.get("approved")
                    or int(vision_review.get("confidence", 0)) < self.config.ai_min_confidence
                ):
                    self.state = "AI_REJECTED"
                    return RuleDecision(
                        reasons.SETUP_REJECTED_BY_AI,
                        skip_reason=str(vision_review.get("reason", reasons.SKIP_AI_REJECTED)),
                    )

            setup = build_setup_object(
                self.symbol, structure, sweep, rectangle, vision_review,
                htf_bias, ob, ob_rectangle_overlap,
            )
            self.state = "RECTANGLE_ACTIVE"
            self.active_setup = setup
            self.active_rectangle = rectangle
            return RuleDecision(reasons.RECTANGLE_ACTIVE_WAITING_FOR_M1, setup=setup)

        self.state = "NO_WEAKNESS_SWEEP"
        return RuleDecision(reasons.NO_SETUP, skip_reason=last_skip or reasons.SKIP_NO_SWEEP)

    def _render_sweep_chart(
        self,
        m15_candles: Sequence[Candle],
        trigger: Candle,
        level_price: float,
        rectangle: object,
        direction: str,
    ) -> Path:
        stamp = trigger.time.strftime("%Y%m%d_%H%M%S")
        output_dir = Path(os.environ.get("VISION_CHARTS_DIR", str(PROJECT_ROOT / "vision_charts")))
        output_path = output_dir / f"{self.symbol}_{stamp}_{direction}.png"
        return render_sweep_chart(
            list(m15_candles),
            trigger,
            level_price,
            rectangle.high,  # type: ignore[attr-defined]
            rectangle.low,  # type: ignore[attr-defined]
            direction,
            output_path,
        )

    def check_m1_flip(self, m1_candles_after_rectangle: Sequence[Candle]) -> RuleDecision:
        if self.active_setup is None or self.active_rectangle is None:
            return RuleDecision(reasons.NO_SETUP)

        eligible_m1 = self._m1_after_m15_close(m1_candles_after_rectangle)
        flip = detect_m1_flip(eligible_m1, self.active_rectangle, self.point, self.config.m1_flip)
        if not flip.confirmed:
            return RuleDecision(reasons.NO_SETUP, setup=self.active_setup, skip_reason=flip.skip_reason)

        entry_price = flip.trigger_candle.close  # type: ignore[union-attr]
        sl, tp = calculate_sl_tp(
            direction=flip.direction,  # type: ignore[arg-type]
            entry_price=entry_price,
            rectangle=self.active_rectangle,
            point=self.point,
            sl_buffer_points=self.config.sl_buffer_points,
            rr=self.config.planned_rr,
        )
        signal = build_entry_signal(
            self.active_setup,
            flip,
            self.active_rectangle,
            entry_price,
            sl,
            tp,
            self.config.planned_rr,
        )
        self.state = "M1_FLIP_CONFIRMED"
        return RuleDecision(reasons.ENTRY_SIGNAL_READY, setup=self.active_setup, entry_signal=signal)

    def _m1_after_m15_close(self, candles: Sequence[Candle]) -> list[Candle]:
        trigger_time = getattr(self.active_rectangle, "trigger_time", None)
        if not isinstance(trigger_time, datetime):
            return list(candles)
        m15_close_time = trigger_time + timedelta(minutes=15)
        return [candle for candle in candles if candle.time >= m15_close_time]


def calculate_sl_tp(
    direction: Literal["buy", "sell"],
    entry_price: float,
    rectangle: object,
    point: float,
    sl_buffer_points: float,
    rr: float,
) -> tuple[float, float]:
    buffer_value = sl_buffer_points * point
    if direction == "buy":
        sl = rectangle.low - buffer_value  # type: ignore[attr-defined]
        distance = entry_price - sl
        tp = entry_price + distance * rr
    else:
        sl = rectangle.high + buffer_value  # type: ignore[attr-defined]
        distance = sl - entry_price
        tp = entry_price - distance * rr
    if distance <= 0:
        raise ValueError("invalid SL distance")
    return sl, tp
