"""MT5 data access through the local MCP server."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from core.candle_builder import Candle, normalize_candle
from core.mt5_mcp_client import Mt5McpClient


class Mt5DataEngine:
    def __init__(self, client: Mt5McpClient | None = None) -> None:
        self.client = client or Mt5McpClient()

    def latest_closed_m15(self, symbol: str, count: int) -> Sequence[Candle]:
        return self.get_candles(symbol, "M15", count, drop_current=True)

    def m1_after(self, symbol: str, start_time: object, max_count: int) -> Sequence[Candle]:
        candles = self.get_candles(symbol, "M1", max_count + 5, drop_current=True)
        if not isinstance(start_time, datetime):
            return candles[:max_count]
        return [candle for candle in candles if candle.time > start_time][:max_count]

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int,
        drop_current: bool = True,
    ) -> list[Candle]:
        response = self.client.call_tool(
            "get_candles",
            {"symbol": symbol, "timeframe": timeframe, "count": count + (1 if drop_current else 0)},
        )
        raw_candles = response.get("candles", [])
        if drop_current and raw_candles:
            raw_candles = raw_candles[:-1]
        return [_normalize_mcp_candle(item, response["symbol"], response["timeframe"]) for item in raw_candles]

    def symbol_info(self, symbol: str) -> dict[str, Any]:
        return self.client.call_tool("symbol_info", {"symbol": symbol})

    def account_info(self) -> dict[str, Any]:
        return self.client.call_tool("get_account", {})


def _normalize_mcp_candle(raw: dict[str, Any], symbol: str, timeframe: str) -> Candle:
    return normalize_candle(
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "time": raw["time"],
            "open": raw["open"],
            "high": raw["high"],
            "low": raw["low"],
            "close": raw["close"],
            "tick_volume": raw.get("volume", 0),
            "spread": raw.get("spread", 0),
            "is_closed": True,
        },
        symbol,
        timeframe,
    )
