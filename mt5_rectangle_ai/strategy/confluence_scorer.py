"""Confluence scoring engine — combines mechanical signals and Claude checklist answers
into a single weighted score that replaces the binary AI approve/reject gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Weight configuration ──────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ConfluenceWeights:
    # Mechanical signals (positive)
    htf_bias_aligned: float = 20.0
    in_kill_zone: float = 20.0
    swept_liquidity_pool: float = 15.0   # double/triple top/bottom or session level
    ob_unmitigated: float = 15.0
    ob_fvg_overlap: float = 10.0
    premium_discount_correct: float = 10.0
    ob_rectangle_overlap: float = 5.0
    ob_h4_timeframe: float = 10.0        # H4 OB is stronger than M15

    # Claude checklist answers (only applied when AI was used)
    claude_clean_sweep: float = 5.0
    claude_ob_visible: float = 5.0
    claude_draw_visible: float = 5.0
    claude_would_trade: float = -999.0   # auto-reject sentinel: never trade without this

    # Penalty criteria (negative)
    ob_mitigation_count_1: float = -10.0
    ob_mitigation_count_2plus: float = -25.0
    outside_kill_zone: float = -30.0


# ── Input / output types ──────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ConfluenceInput:
    # Mechanical signals (always available)
    direction: str                 # "long" / "short"
    htf_bias: str                  # "bullish" / "bearish" / "neutral"
    in_kill_zone: bool
    swept_level_type: str          # single_swing / double_*/triple_*/session_*
    ob_valid: bool
    ob_mitigation_count: int
    ob_fvg_overlap: bool
    ob_rectangle_overlap: bool
    ob_timeframe: str              # "M15" / "H4"
    zone_type: str                 # "premium" / "discount" / "equilibrium"

    # Claude answers — None when AI was not used
    claude_clean_sweep: bool | None = None
    claude_ob_visible: bool | None = None
    claude_draw_visible: bool | None = None
    claude_would_trade: bool | None = None


@dataclass
class ConfluenceResult:
    score: float
    breakdown: dict[str, float]    # criterion name → contribution to score
    auto_rejected: bool            # True when claude_would_trade is False (-999 applied)
    rejection_criterion: str | None = None

    def breakdown_json(self) -> str:
        import json
        return json.dumps(self.breakdown, sort_keys=True)


# ── Scoring logic ─────────────────────────────────────────────────────────────

_POOL_TYPES = frozenset({
    "double_top", "double_bottom",
    "triple_top", "triple_bottom",
    "session_high", "session_low",
})


def compute_confluence_score(
    inp: ConfluenceInput,
    weights: ConfluenceWeights | None = None,
) -> ConfluenceResult:
    """Compute a weighted confluence score from mechanical + AI signals.

    Returns ConfluenceResult with the total score and per-criterion breakdown.
    Auto-rejection fires when claude_would_trade is explicitly False.
    """
    w = weights or ConfluenceWeights()
    breakdown: dict[str, float] = {}
    auto_rejected = False
    rejection_criterion: str | None = None

    # ── Mechanical signals ────────────────────────────────────────────────────

    bias_aligned = (
        (inp.direction == "long" and inp.htf_bias == "bullish") or
        (inp.direction == "short" and inp.htf_bias == "bearish")
    )
    if bias_aligned:
        breakdown["htf_bias_aligned"] = w.htf_bias_aligned

    if inp.in_kill_zone:
        breakdown["in_kill_zone"] = w.in_kill_zone
    else:
        breakdown["outside_kill_zone"] = w.outside_kill_zone

    if inp.swept_level_type in _POOL_TYPES:
        breakdown["swept_liquidity_pool"] = w.swept_liquidity_pool

    if inp.ob_valid:
        if inp.ob_mitigation_count == 0:
            breakdown["ob_unmitigated"] = w.ob_unmitigated
        elif inp.ob_mitigation_count == 1:
            breakdown["ob_mitigation_count_1"] = w.ob_mitigation_count_1
        else:
            breakdown["ob_mitigation_count_2plus"] = w.ob_mitigation_count_2plus

        if inp.ob_fvg_overlap:
            breakdown["ob_fvg_overlap"] = w.ob_fvg_overlap

        if inp.ob_rectangle_overlap:
            breakdown["ob_rectangle_overlap"] = w.ob_rectangle_overlap

        if inp.ob_timeframe == "H4":
            breakdown["ob_h4_timeframe"] = w.ob_h4_timeframe

    pd_correct = (
        (inp.direction == "long" and inp.zone_type == "discount") or
        (inp.direction == "short" and inp.zone_type == "premium")
    )
    if pd_correct:
        breakdown["premium_discount_correct"] = w.premium_discount_correct

    # ── Claude checklist signals (only when AI was used) ──────────────────────

    if inp.claude_would_trade is not None:
        if not inp.claude_would_trade:
            # Auto-reject: apply the sentinel weight and flag
            breakdown["claude_would_trade"] = w.claude_would_trade
            auto_rejected = True
            rejection_criterion = "claude_would_trade"
        # If would_trade is True we don't add a positive weight for it —
        # it's a gate not a bonus. The other Claude criteria carry the weight.

    if inp.claude_clean_sweep is True:
        breakdown["claude_clean_sweep"] = w.claude_clean_sweep

    if inp.claude_ob_visible is True:
        breakdown["claude_ob_visible"] = w.claude_ob_visible

    if inp.claude_draw_visible is True:
        breakdown["claude_draw_visible"] = w.claude_draw_visible

    score = sum(breakdown.values())
    return ConfluenceResult(
        score=score,
        breakdown=breakdown,
        auto_rejected=auto_rejected,
        rejection_criterion=rejection_criterion,
    )


def build_confluence_input(
    setup: dict[str, Any],
    vision_review: dict[str, Any] | None = None,
) -> ConfluenceInput:
    """Assemble a ConfluenceInput from a setup dict (built by signal_builder)."""
    ob = setup.get("order_block", {})
    liq = setup.get("liquidity", {})
    kz = setup.get("kill_zone", {})
    pd = setup.get("premium_discount", {})
    htf = setup.get("htf_bias", {})
    vr = vision_review or {}

    # Claude answers are None unless a v3 AI review was actually performed
    has_ai = vr.get("prompt_version", "auto_approved") not in ("auto_approved", "")
    claude_would_trade = bool(vr["would_trade"]) if has_ai and "would_trade" in vr else None
    claude_clean_sweep = bool(vr["clean_sweep"]) if has_ai and "clean_sweep" in vr else None
    claude_ob_visible = bool(vr["ob_visible"]) if has_ai and "ob_visible" in vr else None
    claude_draw_visible = bool(vr["draw_visible"]) if has_ai and "draw_visible" in vr else None

    return ConfluenceInput(
        direction=str(setup.get("direction", "long")),
        htf_bias=str(htf.get("bias", "neutral")),
        in_kill_zone=bool(kz.get("in_kill_zone", False)),
        swept_level_type=str(liq.get("swept_level_type", "single_swing")),
        ob_valid=bool(ob.get("ob_valid", False)),
        ob_mitigation_count=int(ob.get("ob_mitigation_count", 0)),
        ob_fvg_overlap=bool(ob.get("ob_fvg_overlap", False)),
        ob_rectangle_overlap=bool(ob.get("ob_rectangle_overlap", False)),
        ob_timeframe=str(ob.get("ob_timeframe", "M15")),
        zone_type=str(pd.get("zone_type", "equilibrium")),
        claude_clean_sweep=claude_clean_sweep,
        claude_ob_visible=claude_ob_visible,
        claude_draw_visible=claude_draw_visible,
        claude_would_trade=claude_would_trade,
    )
