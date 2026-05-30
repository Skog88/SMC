"""Claude client boundary.

The rule engine must remain deterministic. This module is only called after a
mechanically valid setup exists, and callers should use only the returned score
and decision for gating.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClaudeConfig:
    model: str = "claude-sonnet"
    timeout_seconds: int = 20


class ClaudeClient:
    def __init__(self, config: ClaudeConfig | None = None) -> None:
        self.config = config or ClaudeConfig()

    def review(self, prompt: str) -> str:
        raise NotImplementedError("Claude API integration belongs in Phase 2")
