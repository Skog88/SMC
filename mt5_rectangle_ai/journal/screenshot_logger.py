"""Compatibility wrapper for screenshot journaling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from journal.journal import Journal


def log_screenshot(setup_id: str, screenshot: dict[str, Any], journal: Journal | None = None) -> None:
    (journal or Journal()).log_screenshot(setup_id, screenshot)


def screenshot_file_path(
    project_root: Path,
    setup_date: str,
    symbol: str,
    direction: str,
    setup_time: str,
    screenshot_type: str,
) -> Path:
    folder = project_root / "data" / "screenshots" / setup_date
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{setup_date}_{symbol}_{direction}_{setup_time}_{screenshot_type}.png"
    return folder / filename
