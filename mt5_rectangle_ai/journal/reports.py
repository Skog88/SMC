"""Basic journal reporting queries."""

from __future__ import annotations

import sqlite3


def setup_counts_by_status(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT state AS status, COUNT(*) AS count FROM setups GROUP BY state ORDER BY count DESC"
    ).fetchall()


def trades_by_symbol(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT symbol, COUNT(*) AS trades, AVG(pnl_r) AS avg_r FROM trades GROUP BY symbol"
    ).fetchall()


def setups_by_final_status(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT final_status, COUNT(*) AS count FROM setups GROUP BY final_status ORDER BY count DESC"
    ).fetchall()
