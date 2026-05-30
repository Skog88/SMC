"""Text-only SMC trade reviewer — uses raw OHLCV candle deltas + narrative instead of chart images.

Advantages over vision:
- No screenshot needed → can review ALL historical setups in backtesting
- Delta encoding is cross-symbol (works for EURUSD and NAS100 identically)
- Claude reasons with exact numbers, not visual approximations
- Faster and cheaper per call

Returns the same AiReviewV3 format as vision_client.py for full compatibility.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from anthropic import Anthropic

from ai.response_parser import parse_v3_response, v3_to_vision_dict
from core.candle_builder import Candle


PROMPT_VERSION = "v3_text_checklist"
_PROMPT_PATH = Path(__file__).parent / "prompt_versions" / "prompt_v3_text_checklist.txt"


# ── Candle encoding ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EncodedCandle:
    idx: int             # relative index (-N to -1, -1 = sweep candle)
    time_str: str
    delta_open: int      # points from swept level
    delta_high: int
    delta_low: int
    delta_close: int
    body_pts: int        # signed: positive = bullish, negative = bearish
    wick_up: int         # points above max(open,close)
    wick_dn: int         # points below min(open,close)
    color: str           # bull / bear / doji
    note: str            # e.g. "[SWEEP]", "[OB]", ""


def encode_candle(
    candle: Candle,
    idx: int,
    swept_level: float,
    point: float,
    note: str = "",
) -> EncodedCandle:
    """Convert one candle to a delta-encoded row relative to the swept level."""
    def pts(price: float) -> int:
        return round((price - swept_level) / point)

    body = candle.close - candle.open
    body_pts = round(body / point)
    wick_up = round((candle.high - max(candle.open, candle.close)) / point)
    wick_dn = round((min(candle.open, candle.close) - candle.low) / point)

    if abs(body_pts) < 2:
        color = "doji"
    elif body_pts > 0:
        color = "bull"
    else:
        color = "bear"

    return EncodedCandle(
        idx=idx,
        time_str=candle.time.strftime("%m-%d %H:%M"),
        delta_open=pts(candle.open),
        delta_high=pts(candle.high),
        delta_low=pts(candle.low),
        delta_close=pts(candle.close),
        body_pts=body_pts,
        wick_up=wick_up,
        wick_dn=wick_dn,
        color=color,
        note=note,
    )


def build_candle_table(rows: list[EncodedCandle]) -> str:
    """Format encoded candles as a compact text table."""
    header = f"{'idx':>4}  {'time':>12}  {'Δo':>6}  {'Δh':>6}  {'Δl':>6}  {'Δc':>6}  {'body':>6}  {'wick↑':>5}  {'wick↓':>5}  {'color':>5}  note"
    lines = [header, "-" * 90]
    for r in rows:
        lines.append(
            f"{r.idx:>4}  {r.time_str:>12}  {r.delta_open:>+6}  {r.delta_high:>+6}  "
            f"{r.delta_low:>+6}  {r.delta_close:>+6}  {r.body_pts:>+6}  {r.wick_up:>5}  "
            f"{r.wick_dn:>5}  {r.color:>5}  {r.note}"
        )
    return "\n".join(lines)


# ── Narrative generation ──────────────────────────────────────────────────────

def generate_narrative(
    rows: list[EncodedCandle],
    direction: str,
    ob_idx: int | None,
    swept_level: float,
) -> str:
    """Generate a concise natural-language description of the candle sequence."""
    if not rows:
        return "No candle context available."

    sweep = next((r for r in rows if "[SWEEP]" in r.note), rows[-1])
    ob = next((r for r in rows if "[OB]" in r.note), None)

    lines: list[str] = []

    # Overall move description
    pre_sweep = [r for r in rows if r.idx < sweep.idx]
    if pre_sweep:
        first, last = pre_sweep[0], pre_sweep[-1]
        net_move = last.delta_close - first.delta_close
        move_dir = "lower" if net_move < 0 else "higher"
        bull_count = sum(1 for r in pre_sweep if r.color == "bull")
        bear_count = sum(1 for r in pre_sweep if r.color == "bear")
        lines.append(
            f"Pre-sweep move ({len(pre_sweep)} candles): price moved {abs(net_move)} pts {move_dir} "
            f"to reach the level ({bull_count} bullish, {bear_count} bearish candles)."
        )

    # OB description
    if ob is not None:
        candles_after_ob = [r for r in rows if ob.idx < r.idx < sweep.idx]
        run_pts = (candles_after_ob[-1].delta_close - ob.delta_close) if candles_after_ob else 0
        lines.append(
            f"Order Block candle at {ob.time_str}: {ob.color}, body={ob.body_pts:+d}pts. "
            f"Followed by {len(candles_after_ob)}-candle run of {abs(run_pts)}pts toward the level."
        )

    # Sweep candle description
    wick = sweep.wick_dn if direction == "long" else sweep.wick_up
    close_side = "above" if sweep.delta_close > 0 else "below"
    lines.append(
        f"Sweep candle at {sweep.time_str}: {sweep.color}, body={sweep.body_pts:+d}pts, "
        f"{'lower' if direction == 'long' else 'upper'} wick={wick}pts through level, "
        f"close={sweep.delta_close:+d}pts ({close_side} level)."
    )

    # Clean sweep signal
    if direction == "long":
        clean = sweep.delta_low < 0 and sweep.delta_close > 0 and wick > abs(sweep.body_pts)
    else:
        clean = sweep.delta_high > 0 and sweep.delta_close < 0 and wick > abs(sweep.body_pts)
    lines.append(f"Sweep quality: {'CLEAN — wick exceeds body, close back inside level' if clean else 'WEAK — close not convincingly back inside, or wick small'}.")

    return " ".join(lines)


# ── Prompt assembly ───────────────────────────────────────────────────────────

def prepare_candle_window(
    m15_candles: Sequence[Candle],
    swept_level: float,
    point: float,
    ob_time: Any | None,
    max_candles: int = 20,
) -> list[EncodedCandle]:
    """Select and encode the most relevant candles for the text prompt."""
    if not m15_candles:
        return []

    candles = list(m15_candles)
    # sweep candle is the last one
    sweep_idx_in_list = len(candles) - 1

    # Take up to max_candles candles ending with the sweep
    start = max(0, sweep_idx_in_list - max_candles + 1)
    window = candles[start:]

    # Find OB candle index in window
    ob_pos_in_window: int | None = None
    if ob_time is not None:
        for i, c in enumerate(window):
            if c.time == ob_time:
                ob_pos_in_window = i
                break

    encoded: list[EncodedCandle] = []
    sweep_window_idx = len(window) - 1  # last candle in window = sweep

    for i, candle in enumerate(window):
        rel_idx = i - sweep_window_idx  # -N to 0 (0 = sweep)
        note = ""
        if i == sweep_window_idx:
            note = "[SWEEP]"
        elif ob_pos_in_window is not None and i == ob_pos_in_window:
            note = "[OB]"
        encoded.append(encode_candle(candle, rel_idx, swept_level, point, note))

    return encoded


def build_text_prompt(
    setup_context: dict[str, Any],
    encoded_candles: list[EncodedCandle],
    swept_level: float,
    direction: str,
    point: float,
    ob_time: Any | None,
) -> str:
    """Assemble the full text-only review prompt."""
    template = _PROMPT_PATH.read_text(encoding="utf-8")

    ob_window_idx = next((r.idx for r in encoded_candles if "[OB]" in r.note), None)
    narrative = generate_narrative(encoded_candles, direction, ob_window_idx, swept_level)
    candle_table = build_candle_table(encoded_candles)

    point_label = f"{point:.5f}" if point < 0.01 else f"{point:.2f}"

    return (
        template
        .replace("{context_json}", json.dumps(setup_context, indent=2))
        .replace("{swept_level_price}", f"{swept_level:.5f}")
        .replace("{direction}", direction)
        .replace("{point_value}", point_label)
        .replace("{candle_table}", candle_table)
        .replace("{narrative}", narrative)
    )


# ── Main reviewer ─────────────────────────────────────────────────────────────

def ask_claude_text(
    m15_candles: Sequence[Candle],
    swept_level: float,
    direction: str,
    point: float,
    setup_context: dict[str, Any],
    ob_time: Any | None = None,
    model: str = "claude-sonnet-4-6",
    max_candles: int = 20,
) -> dict[str, Any]:
    """Text-only SMC review using delta-encoded candles + narrative.

    Returns a dict compatible with state_machine / Phase 7 scorer.
    Same format as vision_client.ask_claude_vision().
    """
    try:
        encoded = prepare_candle_window(m15_candles, swept_level, point, ob_time, max_candles)
        prompt = build_text_prompt(setup_context, encoded, swept_level, direction, point, ob_time)

        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        text = _extract_text(response)
        review = parse_v3_response(text, PROMPT_VERSION)
        result = v3_to_vision_dict(review)
        result["prompt_version"] = PROMPT_VERSION
        return result

    except Exception as exc:
        return {
            "approved": False,
            "confidence": 0,
            "would_trade": False,
            "confluence_count": 0,
            "reason": f"text_review_error: {exc}",
            "prompt_version": PROMPT_VERSION,
        }


def _extract_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []):
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()
