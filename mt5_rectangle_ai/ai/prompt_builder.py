"""Prompt construction for AI vision reviews."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROMPT_DIR = Path(__file__).parent / "prompt_versions"

PROMPT_VERSION_V2 = "v2_quality"
PROMPT_VERSION_V3 = "v3_smc_checklist"
CURRENT_PROMPT_VERSION = PROMPT_VERSION_V3


def build_v3_prompt(setup_context: dict[str, Any]) -> str:
    """Build the v3 SMC checklist prompt with market context injected."""
    template = (_PROMPT_DIR / "prompt_v3_smc_checklist.txt").read_text(encoding="utf-8")
    context_json = json.dumps(setup_context, indent=2)
    return template.replace("{context_json}", context_json)


def build_v2_prompt(symbol: str, direction: str) -> str:
    """Build the legacy v2 quality prompt (frozen — for comparison only)."""
    template = (_PROMPT_DIR / "prompt_v2_quality.txt").read_text(encoding="utf-8")
    return template.replace("{symbol}", symbol).replace("{direction}", direction)


def build_setup_context(
    symbol: str,
    direction: str,
    htf_bias: str | None,
    kill_zone_name: str,
    in_kill_zone: bool,
    swept_level_type: str,
    zone_type: str,
    ob_fvg_overlap: bool,
    ob_mitigation_count: int,
    ob_rectangle_overlap: bool,
) -> dict[str, Any]:
    """Assemble the market context dict that is injected into the v3 prompt."""
    return {
        "symbol": symbol,
        "direction": direction,
        "htf_bias": htf_bias or "neutral",
        "session": kill_zone_name,
        "in_kill_zone": in_kill_zone,
        "swept_level_type": swept_level_type,
        "zone_type": zone_type,
        "ob_fvg_overlap": ob_fvg_overlap,
        "ob_mitigation_count": ob_mitigation_count,
        "ob_rectangle_overlap": ob_rectangle_overlap,
    }
