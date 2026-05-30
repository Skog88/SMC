"""Load config.yaml and resolve per-symbol rule engine configuration."""

from __future__ import annotations

from pathlib import Path

import yaml

from core.htf_engine import HTFConfig
from core.symbol_config import get_symbol_setting
from strategy.m1_flip import M1FlipConfig
from strategy.rectangle import RectangleConfig
from strategy.state_machine import RuleEngineConfig
from strategy.structure_detector import StructureConfig
from strategy.sweep_detector import SweepConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def _resolve(value: object, symbol: str) -> float:
    """Pick the per-category value when value is a dict, else cast to float."""
    if isinstance(value, dict):
        return float(get_symbol_setting(value, symbol))
    return float(value)  # type: ignore[arg-type]


def load_rule_engine_config(symbol: str, config_path: Path | None = None) -> RuleEngineConfig:
    """Return a RuleEngineConfig with all thresholds resolved for *symbol*."""
    path = config_path or _DEFAULT_CONFIG_PATH
    raw: dict = yaml.safe_load(path.read_text(encoding="utf-8"))

    struct_raw = raw.get("structure", {})
    structure = StructureConfig(
        swing_left=int(struct_raw.get("swing_left", 2)),
        swing_right=int(struct_raw.get("swing_right", 2)),
        max_level_age_candles=int(struct_raw.get("max_level_age_candles", 40)),
    )

    sweep = SweepConfig()

    rect_raw = raw.get("rectangle", {})
    rectangle = RectangleConfig(
        min_size_points=_resolve(rect_raw.get("min_size_points", 5), symbol),
        max_size_points=_resolve(rect_raw.get("max_size_points", 200), symbol),
        expires_after_m1_candles=int(rect_raw.get("expires_after_m1_candles", 30)),
    )

    m1_raw = raw.get("m1_flip", {})
    m1_flip = M1FlipConfig(
        require_closed_candle=bool(m1_raw.get("require_closed_candle", True)),
        max_wait_candles=int(m1_raw.get("max_wait_candles", 30)),
        flip_buffer_points=float(m1_raw.get("flip_buffer_points", 0)),
        entry_mode=str(m1_raw.get("entry_mode", "market_after_close")),
    )

    htf_raw = raw.get("htf", {})
    htf_config = HTFConfig(
        timeframe=str(htf_raw.get("timeframe", "H4")),
        swing_left=int(htf_raw.get("swing_left", 3)),
        swing_right=int(htf_raw.get("swing_right", 3)),
        max_bos_age_candles=int(htf_raw.get("max_bos_age_candles", 50)),
        require_confirmed_bos=bool(htf_raw.get("require_confirmed_bos", True)),
    )

    sl_buffer = _resolve(raw.get("sl", {}).get("buffer_points", 5), symbol)
    ai_raw = raw.get("ai", {})
    ai_model = str(ai_raw.get("model", "claude-sonnet-4-6"))
    min_confidence = int(ai_raw.get("min_confidence", 60))
    planned_rr = float(raw.get("tp", {}).get("rr", 3.0))

    return RuleEngineConfig(
        structure=structure,
        sweep=sweep,
        rectangle=rectangle,
        m1_flip=m1_flip,
        htf_config=htf_config,
        ai_model=ai_model,
        ai_min_confidence=min_confidence,
        sl_buffer_points=sl_buffer,
        planned_rr=planned_rr,
    )
