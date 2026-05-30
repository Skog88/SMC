"""Prompt construction for AI scoring after mechanical validation."""

from __future__ import annotations

import json
from typing import Any


PROMPT_VERSION = "rule-engine-v0.1"


def build_review_prompt(ai_request: dict[str, Any]) -> str:
    setup_json = json.dumps(ai_request, indent=2, sort_keys=True)
    return (
        "You are scoring a mechanically valid rectangle-method trading setup.\n"
        "Do not change entry, stop loss, take profit, or risk. Return only valid JSON with "
        "confidence_score, decision, and reasoning. decision must be approve or reject.\n\n"
        f"Setup:\n{setup_json}"
    )
