"""Screenshot path helpers."""

from __future__ import annotations

from pathlib import Path


def setup_screenshot_path(root: Path, setup_id: str) -> Path:
    safe_name = setup_id.replace(":", "-").replace("/", "-").replace("\\", "-")
    path = root / "data" / "screenshots" / f"{safe_name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def dated_screenshot_path(
    root: Path,
    setup_date: str,
    symbol: str,
    direction: str,
    setup_time: str,
    screenshot_type: str,
) -> Path:
    folder = root / "data" / "screenshots" / setup_date
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{setup_date}_{symbol}_{direction}_{setup_time}_{screenshot_type}.png"
    return folder / filename
