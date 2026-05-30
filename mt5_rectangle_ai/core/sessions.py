"""Session helpers and kill zone detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from strategy.session_levels import SessionConfig, SessionWindow, _in_window


def active_sessions(moment: datetime, config: SessionConfig | None = None) -> list[str]:
    cfg = config or SessionConfig()
    clock = moment.timetz().replace(tzinfo=None)
    return [window.name for window in cfg.windows if _in_window(clock, window)]


KillZoneName = Literal["london_open", "new_york_open", "london_close", "none"]


@dataclass(frozen=True, slots=True)
class KillZoneConfig:
    windows: tuple[SessionWindow, ...] = field(default_factory=lambda: (
        SessionWindow("london_open",  time(8,  0), time(10, 0)),
        SessionWindow("new_york_open", time(13, 30), time(15, 30)),
        SessionWindow("london_close",  time(15, 0), time(16, 0)),
    ))
    enabled: bool = True
    hard_filter: bool = False
    timezone: str = "Europe/Oslo"


@dataclass(frozen=True, slots=True)
class KillZoneResult:
    in_kill_zone: bool
    kill_zone_name: KillZoneName


def is_kill_zone(candle_time_utc: datetime, config: KillZoneConfig | None = None) -> KillZoneResult:
    """Return whether a UTC candle time falls inside a configured kill zone.

    candle_time_utc is treated as UTC even if naive (no tzinfo).
    Kill zone windows are defined in Oslo/CET local time and DST is applied
    automatically via zoneinfo.
    """
    cfg = config or KillZoneConfig()
    if not cfg.enabled:
        return KillZoneResult(False, "none")

    # Treat naive datetimes as UTC
    if candle_time_utc.tzinfo is None:
        dt_utc = candle_time_utc.replace(tzinfo=timezone.utc)
    else:
        dt_utc = candle_time_utc.astimezone(timezone.utc)

    dt_local = dt_utc.astimezone(ZoneInfo(cfg.timezone))
    local_time = dt_local.time().replace(tzinfo=None)

    for window in cfg.windows:
        if _in_window(local_time, window):
            return KillZoneResult(True, window.name)  # type: ignore[arg-type]

    return KillZoneResult(False, "none")
