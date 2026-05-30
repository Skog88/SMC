"""Report queries for the feedback loop."""

from __future__ import annotations

import sqlite3


def ai_score_vs_result(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            CASE
                WHEN ai_score < 50 THEN '0-49'
                WHEN ai_score < 60 THEN '50-59'
                WHEN ai_score < 70 THEN '60-69'
                WHEN ai_score < 80 THEN '70-79'
                WHEN ai_score < 90 THEN '80-89'
                ELSE '90-100'
            END AS score_bucket,
            COUNT(*) AS setups,
            SUM(CASE WHEN trade_taken = 1 THEN 1 ELSE 0 END) AS trades,
            AVG(pnl_r) AS avg_r
        FROM ai_training_view
        GROUP BY score_bucket
        ORDER BY score_bucket
        """
    ).fetchall()


def session_performance(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT session, COUNT(*) AS setups, AVG(ai_score) AS avg_ai_score, AVG(t.pnl_r) AS avg_r
        FROM setups s
        LEFT JOIN trades t ON s.setup_id = t.setup_id
        GROUP BY session
        ORDER BY setups DESC
        """
    ).fetchall()


def symbol_performance(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT s.symbol, COUNT(*) AS setups, COUNT(t.trade_id) AS trades, AVG(t.pnl_r) AS avg_r
        FROM setups s
        LEFT JOIN trades t ON s.setup_id = t.setup_id
        GROUP BY s.symbol
        ORDER BY setups DESC
        """
    ).fetchall()
