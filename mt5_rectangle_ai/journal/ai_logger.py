"""Compatibility wrapper for AI review journaling."""

from __future__ import annotations

from typing import Any

from journal.journal import Journal


def log_ai_review(setup_id: str, review: dict[str, Any], journal: Journal | None = None) -> None:
    (journal or Journal()).log_ai_review(setup_id, review)
