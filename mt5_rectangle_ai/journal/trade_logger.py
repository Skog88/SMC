"""Compatibility wrappers for trade journaling."""

from __future__ import annotations

from typing import Any

from journal.journal import Journal


def insert_trade(
    connection_or_journal: object,
    trade_id: str,
    entry_signal: dict[str, Any],
    lot_size: float,
) -> None:
    journal = connection_or_journal if isinstance(connection_or_journal, Journal) else Journal()
    trade = {
        "trade_id": trade_id,
        "symbol": entry_signal["symbol"],
        "direction": entry_signal["direction"],
        "entry_time": entry_signal["m1_trigger_time"],
        "entry_price": entry_signal["entry_price"],
        "sl": entry_signal["sl"],
        "tp": entry_signal["tp"],
        "lot_size": lot_size,
        "planned_rr": entry_signal["planned_rr"],
        "status": "OPEN",
    }
    journal.create_trade(entry_signal["setup_id"], trade)


def close_trade(
    connection_or_journal: object,
    trade_id: str,
    exit_time: str,
    exit_price: float,
    exit_reason: str,
    pnl_money: float,
    pnl_r: float,
) -> None:
    journal = connection_or_journal if isinstance(connection_or_journal, Journal) else Journal()
    journal.update_trade_exit(
        trade_id,
        {
            "exit_time": exit_time,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "net_pnl_money": pnl_money,
            "pnl_r": pnl_r,
            "status": "CLOSED",
        },
    )
