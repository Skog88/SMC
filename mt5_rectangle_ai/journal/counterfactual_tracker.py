"""Counterfactual tracker — silently monitors skipped setups to measure the cost of each filter.

For every rejected setup this module:
  1. Records the planned entry / SL / TP at rejection time.
  2. Monitors subsequent M1 candles (supplied by the caller) to determine
     whether the trade would have hit TP, hit SL, or expired.
  3. Writes the result to the `counterfactuals` table.

The tracker MUST NEVER raise an exception that blocks execution. All public
functions catch and suppress errors internally.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

import sqlite3

from journal.db import connect

logger = logging.getLogger(__name__)

# How many M1 candles to monitor before marking a setup as EXPIRED
_DEFAULT_MONITORING_CANDLES = 240  # 4 hours of M1 bars


@dataclass
class CounterfactualSetup:
    setup_id: str
    skip_reason: str
    direction: str        # "long" / "short"
    planned_entry: float
    planned_sl: float
    planned_tp: float


# ── Public API ────────────────────────────────────────────────────────────────

def record_skip(
    setup_id: str,
    skip_reason: str,
    direction: str,
    planned_entry: float,
    planned_sl: float,
    planned_tp: float,
    db_path: Any = None,
) -> None:
    """Write the initial counterfactual row for a skipped setup.

    Call this synchronously at the point of rejection.  Monitoring is done
    later via resolve_pending() or the async watcher.
    """
    try:
        rr = abs(planned_tp - planned_entry) / abs(planned_entry - planned_sl) if planned_sl != planned_entry else 0.0
        row_id = str(uuid.uuid4())
        now = _utcnow()
        kwargs = dict(db_path=db_path) if db_path else {}
        with connect(**kwargs) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO counterfactuals
                    (id, setup_id, skip_reason, planned_entry, planned_sl, planned_tp,
                     planned_rr, hypothetical_outcome, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
                """,
                (row_id, setup_id, skip_reason, planned_entry, planned_sl, planned_tp, rr, now),
            )
    except Exception:
        logger.exception("counterfactual record_skip failed silently")


def resolve_with_candles(
    setup_id: str,
    m1_candles: Sequence[dict],
    db_path: Any = None,
    max_candles: int = _DEFAULT_MONITORING_CANDLES,
) -> str | None:
    """Replay m1_candles against a pending counterfactual and write the outcome.

    m1_candles must be a sequence of dicts with at minimum:
        {"time": str|datetime, "high": float, "low": float}

    Returns the outcome string or None if no pending row found.
    """
    try:
        kwargs = dict(db_path=db_path) if db_path else {}
        with connect(**kwargs) as conn:
            row = conn.execute(
                """
                SELECT id, direction, planned_entry, planned_sl, planned_tp
                FROM counterfactuals
                WHERE setup_id = ? AND hypothetical_outcome = 'OPEN'
                """,
                (setup_id,),
            ).fetchone()
            if row is None:
                return None

            cf_id = row["id"]
            direction = row["direction"] if "direction" in row.keys() else "long"
            entry = row["planned_entry"]
            sl = row["planned_sl"]
            tp = row["planned_tp"]
            rr = abs(tp - entry) / abs(entry - sl) if sl != entry else 0.0

            outcome, pnl_r, end_time = _replay(direction, entry, sl, tp, rr, m1_candles, max_candles)

            conn.execute(
                """
                UPDATE counterfactuals
                SET hypothetical_outcome = ?,
                    hypothetical_pnl_r = ?,
                    monitoring_end_time = ?
                WHERE id = ?
                """,
                (outcome, pnl_r, end_time, cf_id),
            )
        return outcome
    except Exception:
        logger.exception("counterfactual resolve_with_candles failed silently")
        return None


def resolve_async(
    setup_id: str,
    m1_candles: Sequence[dict],
    db_path: Any = None,
    max_candles: int = _DEFAULT_MONITORING_CANDLES,
) -> None:
    """Non-blocking version of resolve_with_candles — fires and forgets."""
    t = threading.Thread(
        target=resolve_with_candles,
        args=(setup_id, m1_candles),
        kwargs={"db_path": db_path, "max_candles": max_candles},
        daemon=True,
    )
    t.start()


def save_confluence_breakdown(
    setup_id: str,
    breakdown: dict[str, float],
    weights: dict[str, float] | None = None,
    db_path: Any = None,
) -> None:
    """Persist per-criterion confluence breakdown to the confluence_breakdown table.

    breakdown: {criterion: contribution}  (the dict from ConfluenceResult.breakdown)
    weights:   {criterion: weight}        (optional — stored for auditability)
    """
    try:
        now = _utcnow()
        kwargs = dict(db_path=db_path) if db_path else {}
        rows = []
        for criterion, contribution in breakdown.items():
            weight = (weights or {}).get(criterion, 0.0)
            value = 1.0 if contribution != 0 else 0.0
            rows.append((
                str(uuid.uuid4()),
                setup_id,
                criterion,
                value,
                weight,
                contribution,
                now,
            ))
        with connect(**kwargs) as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO confluence_breakdown
                    (id, setup_id, criterion, value, weight, contribution, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
    except Exception:
        logger.exception("save_confluence_breakdown failed silently")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _replay(
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    rr: float,
    candles: Sequence[dict],
    max_candles: int,
) -> tuple[str, float, str]:
    """Walk candles and return (outcome, pnl_r, end_time)."""
    for i, candle in enumerate(candles[:max_candles]):
        high = float(candle["high"])
        low = float(candle["low"])
        t = _candle_time(candle)

        if direction == "long":
            if low <= sl:
                return "SL_HIT", -1.0, t
            if high >= tp:
                return "TP_HIT", rr, t
        else:
            if high >= sl:
                return "SL_HIT", -1.0, t
            if low <= tp:
                return "TP_HIT", rr, t

    last_time = _candle_time(candles[-1]) if candles else _utcnow()
    return "EXPIRED", 0.0, last_time


def _candle_time(candle: dict) -> str:
    t = candle.get("time", "")
    if isinstance(t, datetime):
        return t.isoformat()
    return str(t)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
