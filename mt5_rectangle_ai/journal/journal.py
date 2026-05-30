"""High-level journal interface.

Only this layer should write directly to SQLite. Methods are defensive: failed
SQLite writes are mirrored to emergency JSONL so trading flow can continue when
safe.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from journal.db import DEFAULT_DB_PATH, PROJECT_ROOT, connect, initialize_database


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class Journal:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH, project_root: Path = PROJECT_ROOT) -> None:
        self.db_path = Path(db_path)
        self.project_root = project_root
        initialize_database(self.db_path)

    def create_setup(self, setup: dict[str, Any]) -> None:
        self._safe_write("SETUP_CREATED", setup, self._create_setup, setup)

    def update_setup_state(
        self,
        setup_id: str,
        state: str,
        final_status: str | None = None,
        skip_reason: str | None = None,
        skip_stage: str | None = None,
    ) -> None:
        payload = {
            "setup_id": setup_id,
            "state": state,
            "final_status": final_status,
            "skip_reason": skip_reason,
            "skip_stage": skip_stage,
        }
        self._safe_write("SETUP_STATE_UPDATED", payload, self._update_setup_state, **payload)

    def log_ai_review(self, setup_id: str, review: dict[str, Any]) -> None:
        payload = {"setup_id": setup_id, **review}
        self._safe_write("AI_REVIEW_LOGGED", payload, self._log_ai_review, setup_id, review)

    def log_m1_event(self, setup_id: str, event: dict[str, Any]) -> None:
        payload = {"setup_id": setup_id, **event}
        self._safe_write("M1_EVENT_LOGGED", payload, self._log_m1_event, setup_id, event)

    def create_trade(self, setup_id: str, trade: dict[str, Any]) -> None:
        payload = {"setup_id": setup_id, **trade}
        self._safe_write("TRADE_CREATED", payload, self._create_trade, setup_id, trade)

    def update_trade_exit(self, trade_id: str, exit_data: dict[str, Any]) -> None:
        payload = {"trade_id": trade_id, **exit_data}
        self._safe_write("TRADE_EXIT_UPDATED", payload, self._update_trade_exit, trade_id, exit_data)

    def log_trade_event(self, trade_id: str, event: dict[str, Any]) -> None:
        payload = {"trade_id": trade_id, **event}
        self._safe_write("TRADE_EVENT_LOGGED", payload, self._log_trade_event, trade_id, event)

    def log_screenshot(self, setup_id: str, screenshot: dict[str, Any]) -> None:
        payload = {"setup_id": setup_id, **screenshot}
        self._safe_write("SCREENSHOT_LOGGED", payload, self._log_screenshot, setup_id, screenshot)

    def log_system_event(
        self,
        component: str,
        severity: str,
        event_type: str,
        message: str,
        raw: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "component": component,
            "severity": severity,
            "event_type": event_type,
            "message": message,
            "raw": raw,
        }
        self._safe_write("SYSTEM_EVENT_LOGGED", payload, self._log_system_event, component, severity, event_type, message, raw)

    def backup_daily(self, backup_date: date | None = None, keep_last: int = 30) -> Path:
        backup_day = backup_date or date.today()
        backup_dir = self.project_root / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"journal_{backup_day.isoformat()}.sqlite"
        shutil.copy2(self.db_path, backup_path)
        backups = sorted(backup_dir.glob("journal_*.sqlite"), key=lambda path: path.stat().st_mtime, reverse=True)
        for old_backup in backups[keep_last:]:
            old_backup.unlink(missing_ok=True)
        return backup_path

    def _safe_write(self, event_name: str, payload: dict[str, Any], operation: Callable[..., None], *args: Any, **kwargs: Any) -> None:
        try:
            operation(*args, **kwargs)
        except Exception as exc:  # keep journal failures from taking down scanning/exits
            fallback = {
                "time": utc_now(),
                "event": event_name,
                "error": str(exc),
                "payload": payload,
            }
            self._write_emergency_jsonl(fallback)

    def _write_emergency_jsonl(self, payload: dict[str, Any]) -> None:
        folder = self.project_root / "data" / "emergency_logs"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"journal_fallback_{date.today().isoformat()}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str, sort_keys=True) + "\n")

    def _create_setup(self, setup: dict[str, Any]) -> None:
        now = utc_now()
        trend = setup.get("trend", {})
        structure = setup.get("structure", {})
        sweep = setup.get("sweep", {})
        rectangle = setup.get("rectangle", {})
        setup_time = setup.get("setup_time") or sweep.get("trigger_time") or now
        setup_date = str(setup_time)[:10]
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO setups (
                    setup_id, symbol, direction, setup_time, setup_date, session,
                    timeframe_setup, timeframe_entry, state, final_status,
                    ema_primary_period, ema_secondary_period, ema_primary_value, ema_secondary_value,
                    price_vs_ema, ema_slope_points, trend_direction, trend_valid,
                    marked_level_type, marked_level_price, marked_level_time, clean_structure,
                    structure_score, level_age_candles, level_already_swept,
                    inside_imbalance, imbalance_type, imbalance_low, imbalance_high, imbalance_distance_points,
                    level_is_session_high_low, related_session, related_session_level, session_level_distance_points,
                    m15_trigger_time, m15_open, m15_high, m15_low, m15_close, m15_tick_volume,
                    sweep_valid, sweep_depth_points, wick_size_points, wick_to_range_ratio, close_position,
                    rectangle_low, rectangle_high, rectangle_size_points,
                    ai_enabled, ai_score, ai_decision, ai_model, ai_prompt_version,
                    skip_reason, skip_stage, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(setup_id) DO UPDATE SET
                    state=excluded.state,
                    final_status=excluded.final_status,
                    ai_score=excluded.ai_score,
                    ai_decision=excluded.ai_decision,
                    skip_reason=excluded.skip_reason,
                    skip_stage=excluded.skip_stage,
                    updated_at=excluded.updated_at
                """,
                (
                    setup["setup_id"],
                    setup["symbol"],
                    setup["direction"],
                    setup_time,
                    setup_date,
                    structure.get("session") or setup.get("session"),
                    setup.get("timeframe_setup", "M15"),
                    setup.get("timeframe_entry", "M1"),
                    setup.get("state", "M15_WEAKNESS_CONFIRMED"),
                    setup.get("final_status"),
                    setup.get("ema_primary_period", 50),
                    setup.get("ema_secondary_period", 200),
                    trend.get("ema_50"),
                    trend.get("ema_200"),
                    trend.get("price_vs_ema"),
                    trend.get("slope_points") or trend.get("ema_slope_points"),
                    setup.get("direction"),
                    int(bool(trend.get("trend_valid"))),
                    structure.get("marked_level_type"),
                    structure.get("marked_level_price"),
                    structure.get("level_time"),
                    int(bool(structure.get("clean_structure"))),
                    structure.get("structure_score"),
                    structure.get("level_age_candles"),
                    int(bool(structure.get("level_already_swept", False))),
                    int(bool(structure.get("inside_imbalance"))),
                    structure.get("imbalance_type"),
                    structure.get("imbalance_low"),
                    structure.get("imbalance_high"),
                    structure.get("imbalance_distance_points"),
                    int(bool(structure.get("session_high_low"))),
                    structure.get("session"),
                    structure.get("related_session_level"),
                    structure.get("session_level_distance_points"),
                    sweep.get("trigger_time"),
                    sweep.get("open"),
                    sweep.get("high"),
                    sweep.get("low"),
                    sweep.get("close"),
                    sweep.get("tick_volume"),
                    int(bool(sweep.get("valid_weakness"))),
                    sweep.get("sweep_depth_points"),
                    sweep.get("wick_size_points"),
                    sweep.get("wick_to_range_ratio"),
                    sweep.get("close_position"),
                    rectangle.get("low"),
                    rectangle.get("high"),
                    rectangle.get("size_points"),
                    int(bool(setup.get("ai_enabled", False))),
                    setup.get("ai_score"),
                    setup.get("ai_decision"),
                    setup.get("ai_model"),
                    setup.get("ai_prompt_version"),
                    setup.get("skip_reason"),
                    setup.get("skip_stage"),
                    now,
                    now,
                ),
            )

    def _update_setup_state(
        self,
        setup_id: str,
        state: str,
        final_status: str | None = None,
        skip_reason: str | None = None,
        skip_stage: str | None = None,
    ) -> None:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                UPDATE setups
                SET state = ?, final_status = COALESCE(?, final_status),
                    skip_reason = COALESCE(?, skip_reason),
                    skip_stage = COALESCE(?, skip_stage),
                    updated_at = ?
                WHERE setup_id = ?
                """,
                (state, final_status, skip_reason, skip_stage, utc_now(), setup_id),
            )

    def _log_ai_review(self, setup_id: str, review: dict[str, Any]) -> None:
        now = utc_now()
        parsed_json = review.get("parsed_json")
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO ai_reviews (
                    review_id, setup_id, provider, model, prompt_version, input_json,
                    raw_response, parsed_json, confidence_score, decision, reasoning,
                    response_valid, error_message, latency_ms, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.get("review_id", make_id("ai")),
                    setup_id,
                    review.get("provider", "claude"),
                    review.get("model"),
                    review.get("prompt_version"),
                    _json(review.get("input_json", {})),
                    review.get("raw_response"),
                    _json(parsed_json) if isinstance(parsed_json, (dict, list)) else parsed_json,
                    review.get("confidence_score"),
                    review.get("decision"),
                    review.get("reasoning"),
                    int(bool(review.get("response_valid", True))),
                    review.get("error_message"),
                    review.get("latency_ms"),
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE setups
                SET ai_enabled = 1, ai_score = ?, ai_decision = ?, ai_model = ?,
                    ai_prompt_version = ?, updated_at = ?
                WHERE setup_id = ?
                """,
                (
                    review.get("confidence_score"),
                    review.get("decision"),
                    review.get("model"),
                    review.get("prompt_version"),
                    now,
                    setup_id,
                ),
            )

    def _log_m1_event(self, setup_id: str, event: dict[str, Any]) -> None:
        now = utc_now()
        candle = event.get("candle", event)
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO m1_events (
                    event_id, setup_id, symbol, direction, m1_time, m1_open, m1_high,
                    m1_low, m1_close, m1_tick_volume, rectangle_low, rectangle_high,
                    close_above_rectangle, close_below_rectangle, touched_rectangle,
                    entered_rectangle, flip_confirmed, event_type, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.get("event_id", make_id("m1")),
                    setup_id,
                    event["symbol"],
                    event["direction"],
                    event.get("m1_time") or candle.get("time"),
                    candle.get("open"),
                    candle.get("high"),
                    candle.get("low"),
                    candle.get("close"),
                    candle.get("tick_volume"),
                    event.get("rectangle_low"),
                    event.get("rectangle_high"),
                    int(bool(event.get("close_above_rectangle"))),
                    int(bool(event.get("close_below_rectangle"))),
                    int(bool(event.get("touched_rectangle"))),
                    int(bool(event.get("entered_rectangle"))),
                    int(bool(event.get("flip_confirmed"))),
                    event.get("event_type", "M1_WAITING"),
                    now,
                ),
            )
            if event.get("flip_confirmed"):
                connection.execute(
                    """
                    UPDATE setups
                    SET m1_flip_confirmed = 1, m1_flip_time = ?, m1_flip_close = ?,
                        m1_wait_candles = COALESCE(?, m1_wait_candles), updated_at = ?
                    WHERE setup_id = ?
                    """,
                    (event.get("m1_time") or candle.get("time"), candle.get("close"), event.get("m1_wait_candles"), now, setup_id),
                )

    def _create_trade(self, setup_id: str, trade: dict[str, Any]) -> None:
        now = utc_now()
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO trades (
                    trade_id, setup_id, symbol, direction, mt5_order_id, mt5_deal_id,
                    mt5_position_id, entry_time, entry_price, requested_entry_price, sl, tp,
                    lot_size, risk_money, risk_percent, planned_rr, sl_distance_points,
                    tp_distance_points, spread_at_entry_points, slippage_points, commission,
                    swap, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.get("trade_id") or f"{setup_id}_TRADE_{trade.get('mt5_position_id', 'PENDING')}",
                    setup_id,
                    trade["symbol"],
                    trade["direction"],
                    trade.get("mt5_order_id"),
                    trade.get("mt5_deal_id"),
                    trade.get("mt5_position_id"),
                    trade.get("entry_time"),
                    trade.get("entry_price"),
                    trade.get("requested_entry_price"),
                    trade.get("sl"),
                    trade.get("tp"),
                    trade.get("lot_size"),
                    trade.get("risk_money"),
                    trade.get("risk_percent"),
                    trade.get("planned_rr"),
                    trade.get("sl_distance_points"),
                    trade.get("tp_distance_points"),
                    trade.get("spread_at_entry_points"),
                    trade.get("slippage_points"),
                    trade.get("commission"),
                    trade.get("swap"),
                    trade.get("status", "OPEN"),
                    now,
                    now,
                ),
            )
            connection.execute(
                "UPDATE setups SET execution_attempted = 1, order_sent = 1, final_status = ?, updated_at = ? WHERE setup_id = ?",
                ("TRADE_OPENED", now, setup_id),
            )

    def _update_trade_exit(self, trade_id: str, exit_data: dict[str, Any]) -> None:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                UPDATE trades
                SET exit_time = ?, exit_price = ?, exit_reason = ?, gross_pnl_money = ?,
                    net_pnl_money = ?, pnl_r = ?, max_favorable_excursion_points = ?,
                    max_adverse_excursion_points = ?, max_favorable_r = ?, max_adverse_r = ?,
                    duration_minutes = ?, status = ?, updated_at = ?
                WHERE trade_id = ?
                """,
                (
                    exit_data.get("exit_time"),
                    exit_data.get("exit_price"),
                    exit_data.get("exit_reason"),
                    exit_data.get("gross_pnl_money"),
                    exit_data.get("net_pnl_money"),
                    exit_data.get("pnl_r"),
                    exit_data.get("max_favorable_excursion_points"),
                    exit_data.get("max_adverse_excursion_points"),
                    exit_data.get("max_favorable_r"),
                    exit_data.get("max_adverse_r"),
                    exit_data.get("duration_minutes"),
                    exit_data.get("status", "CLOSED"),
                    utc_now(),
                    trade_id,
                ),
            )

    def _log_trade_event(self, trade_id: str, event: dict[str, Any]) -> None:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO trade_events (
                    event_id, trade_id, setup_id, event_time, event_type, price,
                    volume, mt5_raw_json, message, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.get("event_id", make_id("trade_event")),
                    trade_id,
                    event["setup_id"],
                    event.get("event_time", utc_now()),
                    event["event_type"],
                    event.get("price"),
                    event.get("volume"),
                    _json(event.get("mt5_raw_json")),
                    event.get("message"),
                    utc_now(),
                ),
            )

    def _log_screenshot(self, setup_id: str, screenshot: dict[str, Any]) -> None:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO screenshots (
                    screenshot_id, setup_id, trade_id, symbol, timeframe,
                    screenshot_type, file_path, chart_time, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    screenshot.get("screenshot_id", make_id("shot")),
                    setup_id,
                    screenshot.get("trade_id"),
                    screenshot["symbol"],
                    screenshot["timeframe"],
                    screenshot["screenshot_type"],
                    screenshot["file_path"],
                    screenshot.get("chart_time"),
                    utc_now(),
                ),
            )

    def _log_system_event(
        self,
        component: str,
        severity: str,
        event_type: str,
        message: str,
        raw: dict[str, Any] | None = None,
    ) -> None:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO system_events (
                    event_id, event_time, component, severity, event_type,
                    message, raw_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (make_id("system"), utc_now(), component, severity, event_type, message, _json(raw), utc_now()),
            )


def _json(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str, sort_keys=True)
