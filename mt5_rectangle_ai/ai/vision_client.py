"""Claude vision review — v3 SMC checklist (falls back to v2 for legacy callers)."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from ai.prompt_builder import (
    CURRENT_PROMPT_VERSION,
    build_v2_prompt,
    build_v3_prompt,
)
from ai.response_parser import parse_v3_response, v3_to_vision_dict


def ask_claude_vision(
    image_path: Path,
    direction: str,
    symbol: str,
    setup_context: dict[str, Any] | None = None,
    model: str = "claude-sonnet-4-6",
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Send a chart to Claude for SMC checklist review.

    When setup_context is provided, uses v3 prompt (structured checklist).
    Without it falls back to legacy v2 behaviour.
    Returns a dict compatible with state_machine approval checks.
    """
    try:
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")

        if setup_context is not None:
            prompt = build_v3_prompt(setup_context)
            prompt_version = CURRENT_PROMPT_VERSION
        else:
            prompt = build_v2_prompt(symbol, direction)
            prompt_version = "v2_quality"

        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        text = _response_text(response)

        if setup_context is not None:
            review = parse_v3_response(text, prompt_version)
            return v3_to_vision_dict(review)
        else:
            return _parse_v2_json(text)

    except Exception as exc:
        return {
            "approved": False,
            "confidence": 0,
            "would_trade": False,
            "confluence_count": 0,
            "reason": f"vision_error: {exc}",
            "prompt_version": prompt_version if "prompt_version" in dir() else "unknown",
        }


def _response_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []):
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _parse_v2_json(text: str) -> dict[str, Any]:
    import json
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"approved": False, "reason": "parse_error", "confidence": 0,
                "prompt_version": "v2_quality"}
    return {
        "approved": bool(data.get("approved", False)),
        "confidence": int(data.get("confidence", 0)),
        "reason": str(data.get("reason", "")),
        "prompt_version": "v2_quality",
    }
