"""Execution-engine boundary for finalized order tickets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.mt5_mcp_client import Mt5McpClient


@dataclass(frozen=True, slots=True)
class OrderTicket:
    symbol: str
    direction: Literal["buy", "sell"]
    entry_type: str
    lot_size: float
    entry_price: float
    sl: float
    tp: float
    setup_id: str


class Mt5Executor:
    def __init__(self, client: Mt5McpClient | None = None) -> None:
        self.client = client or Mt5McpClient()

    def send_order(self, ticket: OrderTicket) -> str:
        response = self.client.call_tool(
            "place_order",
            {
                "symbol": ticket.symbol,
                "direction": ticket.direction,
                "volume": ticket.lot_size,
                "sl": ticket.sl,
                "tp": ticket.tp,
            },
        )
        return str(response["ticket"])
