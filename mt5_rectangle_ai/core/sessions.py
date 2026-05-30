"""Session helpers."""

from __future__ import annotations

from datetime import datetime

from strategy.session_levels import SessionConfig, _in_window


def active_sessions(moment: datetime, config: SessionConfig | None = None) -> list[str]:
    cfg = config or SessionConfig()
    clock = moment.timetz().replace(tzinfo=None)
    return [window.name for window in cfg.windows if _in_window(clock, window)]
