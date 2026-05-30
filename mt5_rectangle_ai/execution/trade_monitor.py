"""Position monitoring boundary."""

from __future__ import annotations

from dataclasses import dataclass

from core.mt5_mcp_client import Mt5McpClient


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    position_id: str
    symbol: str
    volume: float
    price_open: float
    price_current: float
    profit: float


class TradeMonitor:
    def __init__(self, client: Mt5McpClient | None = None) -> None:
        self.client = client or Mt5McpClient()

    def open_positions(self) -> list[dict]:
        response = self.client.call_tool("get_positions", {})
        return response.get("positions", []) if isinstance(response, dict) else []

    def snapshot(self, position_id: str) -> PositionSnapshot:
        for position in self.open_positions():
            if str(position["ticket"]) == str(position_id):
                return PositionSnapshot(
                    position_id=str(position["ticket"]),
                    symbol=position["symbol"],
                    volume=float(position["volume"]),
                    price_open=float(position["open_price"]),
                    price_current=float(position["current_price"]),
                    profit=float(position["pnl"]),
                )
        raise LookupError(f"position {position_id} is not open")
