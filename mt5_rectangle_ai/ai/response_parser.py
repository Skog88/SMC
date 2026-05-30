"""Parse and validate AI review responses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AiReview:
    confidence_score: int
    decision: str
    reasoning: str
    raw_response: str


def parse_ai_review(raw_response: str) -> AiReview:
    payload: dict[str, Any] = json.loads(raw_response)
    score = int(payload["confidence_score"])
    decision = str(payload["decision"]).lower()
    if decision not in {"approve", "reject"}:
        raise ValueError("AI decision must be approve or reject")
    if not 0 <= score <= 100:
        raise ValueError("AI confidence_score must be between 0 and 100")
    return AiReview(score, decision, str(payload.get("reasoning", "")), raw_response)
