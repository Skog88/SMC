"""Claude vision review for rendered weakness-sweep charts."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from anthropic import Anthropic


def ask_claude_vision(
    image_path: Path,
    direction: str,
    symbol: str,
) -> dict[str, Any]:
    """Ask Claude to approve or reject a rendered sweep chart."""
    try:
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        prompt = (
            "You are a rules-based quality checker for one specific trading pattern: the M15 weakness sweep.\n\n"
            "The mechanical system has already confirmed:\n"
            "- A swing high or low was identified on the 15-minute chart\n"
            "- The candle wicked through that level\n"
            "- The candle closed back inside (rejection)\n"
            "- The candle colour is correct (bearish candle for a low sweep, bullish for a high sweep)\n"
            "- The rectangle is drawn from the candle close to the candle wick extreme\n\n"
            "Your job is NOT to re-check those mechanics. They already passed.\n"
            "Your job is to assess QUALITY. Approve if the setup looks clean. Reject if it looks like noise.\n\n"
            f"Symbol: {symbol}\n"
            f"Direction: {direction}\n"
            "The dashed line = the swept level.\n"
            "The shaded box = the rectangle (entry zone).\n\n"
            "APPROVE if ALL of these are true:\n"
            "- The swept level was a clear, identifiable swing point (not mid-range noise)\n"
            "- The sweep candle is proportionate, not a massive spike candle with an enormous wick\n"
            "- The rectangle is large enough to trade (the box is visible and meaningful on the chart)\n"
            "- Price was moving toward the level before the sweep, not chopping sideways around it for many candles\n\n"
            "REJECT if ANY of these are true:\n"
            "- The level is not visually obvious, it looks like random price, not a real swing\n"
            "- The sweep candle is a huge spike (wick many times larger than surrounding candles)\n"
            "- The rectangle is a thin sliver, too small to place a real stop loss\n"
            "- Price has been ranging and chopping around the level for many candles before the sweep\n"
            "- The same level has been wicked through multiple times already without a clean move away\n\n"
            "Do NOT reject based on:\n"
            "- General market direction or momentum\n"
            "- Whether a trend looks extended\n"
            "- Any fundamental or news reasoning\n"
            "- Uncertainty about what price might do next\n\n"
            "Respond in JSON only:\n"
            '{"approved": true/false, "confidence": 0-100, "reason": "one sentence, reference what you saw"}'
        )

        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
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
        return _parse_json(text)
    except Exception as exc:
        return {"approved": False, "reason": f"vision_error: {exc}", "confidence": 0}


def _response_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []):
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"approved": False, "reason": "parse_error", "confidence": 0}
    return {
        "approved": bool(data.get("approved", False)),
        "confidence": int(data.get("confidence", 0)),
        "reason": str(data.get("reason", "")),
    }
