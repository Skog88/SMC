"""Parse and validate AI review responses — supports v2 (legacy) and v3 (SMC checklist)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AiReviewV3:
    """Structured result from a v3 SMC checklist review."""
    clean_sweep: bool
    liquidity_pool: bool
    fvg_present: bool
    ob_visible: bool
    htf_confirmed: bool
    draw_visible: bool
    would_trade: bool
    confluence_count: int
    rejection_reason: str | None
    prompt_version: str
    raw_response: str

    @property
    def approved(self) -> bool:
        return self.would_trade

    @property
    def confidence(self) -> int:
        return self.confluence_count


# Legacy v2 dataclass kept for backward compat
@dataclass(frozen=True, slots=True)
class AiReview:
    confidence_score: int
    decision: str
    reasoning: str
    raw_response: str


def parse_v3_response(raw: str, prompt_version: str = "v3_smc_checklist") -> AiReviewV3:
    """Parse a v3 checklist JSON response. Raises ValueError on invalid input."""
    cleaned = _clean_json(raw)
    data: dict[str, Any] = json.loads(cleaned)

    answers: dict[str, Any] = data.get("answers", {})
    criteria = ("clean_sweep", "liquidity_pool", "fvg_present", "ob_visible",
                "htf_confirmed", "draw_visible", "would_trade")

    bool_answers = {k: bool(answers.get(k, False)) for k in criteria}
    confluence_count = int(data.get("confluence_count", sum(bool_answers.values())))

    return AiReviewV3(
        clean_sweep=bool_answers["clean_sweep"],
        liquidity_pool=bool_answers["liquidity_pool"],
        fvg_present=bool_answers["fvg_present"],
        ob_visible=bool_answers["ob_visible"],
        htf_confirmed=bool_answers["htf_confirmed"],
        draw_visible=bool_answers["draw_visible"],
        would_trade=bool_answers["would_trade"],
        confluence_count=confluence_count,
        rejection_reason=data.get("rejection_reason"),
        prompt_version=prompt_version,
        raw_response=raw,
    )


def parse_ai_review(raw_response: str) -> AiReview:
    """Legacy v2 parser kept for backward compatibility."""
    payload: dict[str, Any] = json.loads(raw_response)
    score = int(payload["confidence_score"])
    decision = str(payload["decision"]).lower()
    if decision not in {"approve", "reject"}:
        raise ValueError("AI decision must be approve or reject")
    if not 0 <= score <= 100:
        raise ValueError("AI confidence_score must be between 0 and 100")
    return AiReview(score, decision, str(payload.get("reasoning", "")), raw_response)


def v3_to_vision_dict(review: AiReviewV3) -> dict[str, Any]:
    """Convert a v3 review into the dict format expected by state_machine / signal_builder."""
    return {
        "approved": review.approved,
        "confidence": review.confidence,
        "would_trade": review.would_trade,
        "confluence_count": review.confluence_count,
        "clean_sweep": review.clean_sweep,
        "liquidity_pool": review.liquidity_pool,
        "fvg_present": review.fvg_present,
        "ob_visible": review.ob_visible,
        "htf_confirmed": review.htf_confirmed,
        "draw_visible": review.draw_visible,
        "rejection_reason": review.rejection_reason,
        "prompt_version": review.prompt_version,
        "reason": review.rejection_reason or "approved",
    }


def _clean_json(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # strip first and last fence lines
        inner = lines[1:] if lines[0].startswith("```") else lines
        inner = inner[:-1] if inner and inner[-1].strip() == "```" else inner
        cleaned = "\n".join(inner).strip()
    return cleaned
