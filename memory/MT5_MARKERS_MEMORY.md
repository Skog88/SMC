# MT5 Marker Indicator Memory

Purpose:

Display GBPUSD backtest trades directly on the MT5 chart.

## Why Indicator Was Needed

The current MT5 MCP server at:

`C:\mt5-mcp\mt5_mcp_server.py`

does not expose chart drawing/object tools.

Workaround:

- create an MT5 custom indicator.
- indicator reads a CSV from `MQL5\Files`.
- indicator draws objects on the chart.

## Files

Terminal data path:

`C:\Users\m080p\AppData\Roaming\MetaQuotes\Terminal\930119AA53207C8778B41171FBFFB46F`

Indicator:

- `MQL5\Indicators\RectangleBacktestMarkers.mq5`
- `MQL5\Indicators\RectangleBacktestMarkers.ex5`

CSV:

- `MQL5\Files\GBPUSD_rectangle_backtest_trades.csv`

## Behavior

The indicator draws:

- entry arrows.
- exit arrows.
- entry labels.
- exit labels.
- horizontal entry segments.
- SL dotted segments.
- TP dashed segments.
- top-left dashboard label.

The vertical entry/exit lines were removed because they made candle wicks hard to see.

## Debug History

Initial issue:

- MT5 log said indicator loaded successfully.
- No markers were visible.

Cause 1:

- markers were off-screen.
- indicator was updated to auto-jump to first trade.

Cause 2:

- MT5 parsed CSV formatted date strings incorrectly.
- logs showed first trade as `2026.05.03 00:00`.

Cause 3:

- manual string parser still failed.
- logs showed objects near `1970.01.01`.

Final fix:

- marker CSV was changed to Unix timestamp seconds.
- indicator detects numeric timestamps and casts directly to `datetime`.

Current status:

- user confirmed markers are visible.
- vertical lines removed.
- indicator recompiled with `0 errors, 0 warnings`.

## Recompile Command

```powershell
& 'C:\Program Files\Fusion Markets MetaTrader 5\metaeditor64.exe' /compile:'C:\Users\m080p\AppData\Roaming\MetaQuotes\Terminal\930119AA53207C8778B41171FBFFB46F\MQL5\Indicators\RectangleBacktestMarkers.mq5' /log:'C:\Users\m080p\AppData\Roaming\MetaQuotes\Terminal\930119AA53207C8778B41171FBFFB46F\MQL5\Logs\RectangleBacktestMarkers_compile.log'
```
