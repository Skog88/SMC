"""Client wrapper for the local MT5 MCP stdio server."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@dataclass(frozen=True, slots=True)
class Mt5McpConfig:
    server_script: Path = Path("C:/mt5-mcp/mt5_mcp_server.py")
    python_executable: str = "python"
    timeout_seconds: float = 30.0


class Mt5McpError(RuntimeError):
    pass


class Mt5McpClient:
    """Thin client for one-shot MCP tool calls.

    This keeps strategy code independent from MT5 and from the MCP transport.
    Long-running daemons can later keep a persistent session open for efficiency.
    """

    def __init__(self, config: Mt5McpConfig | None = None) -> None:
        self.config = config or Mt5McpConfig()

    async def call_tool_async(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        params = StdioServerParameters(
            command=self.config.python_executable,
            args=[str(self.config.server_script)],
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments or {})

        text = "\n".join(
            item.text for item in result.content if getattr(item, "type", None) == "text"
        ).strip()
        if not text:
            return None
        if text.startswith("{") or text.startswith("["):
            return json.loads(text)
        raise Mt5McpError(text)

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return anyio.run(self.call_tool_async, name, arguments or {})
