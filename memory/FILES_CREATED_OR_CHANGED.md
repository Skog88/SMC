# Files Created or Changed

## Main Project

Root:
- `C:\15m-1m\mt5_rectangle_ai\main.py`
- `C:\15m-1m\mt5_rectangle_ai\config.yaml` ← updated 2026-05-03: per-category thresholds, US100→NAS100
- `C:\15m-1m\mt5_rectangle_ai\requirements.txt`

Core:
- `core\__init__.py`
- `core\candle_builder.py`
- `core\data_engine.py`
- `core\mt5_mcp_client.py`
- `core\sessions.py`
- `core\symbol_config.py`
- `core\config_loader.py` ← NEW 2026-05-03: loads config.yaml, resolves per-symbol thresholds

Strategy:
- `strategy\__init__.py`
- `strategy\ema_filter.py`
- `strategy\structure_detector.py`
- `strategy\imbalance_detector.py`
- `strategy\session_levels.py`
- `strategy\sweep_detector.py`
- `strategy\rectangle.py`
- `strategy\m1_flip.py`
- `strategy\signal_builder.py`
- `strategy\skip_reasons.py`
- `strategy\state_machine.py`

AI:
- `ai\__init__.py`
- `ai\claude_client.py`
- `ai\prompt_builder.py`
- `ai\response_parser.py`

Execution:
- `execution\__init__.py`
- `execution\mt5_executor.py`
- `execution\position_sizer.py`
- `execution\risk_engine.py`
- `execution\trade_monitor.py`

Journal:
- `journal\__init__.py`
- `journal\db.py`
- `journal\schema.sql`
- `journal\journal.py`
- `journal\setup_logger.py`
- `journal\ai_logger.py`
- `journal\trade_logger.py`
- `journal\screenshot.py`
- `journal\screenshot_logger.py`
- `journal\reports.py`
- `journal\report_builder.py`
- `journal\exporters.py`

Dashboard:
- `dashboards\local_dashboard.py`

Backtesting:
- `backtesting\__init__.py`
- `backtesting\mechanical_backtest.py` ← updated 2026-05-03: uses config_loader
- `backtesting\generate_tv_indicator.py` ← NEW 2026-05-03: generates TradingView Pine Script

Data folders:
- `data\journal.sqlite`
- `data\screenshots`
- `data\reports`
- `data\reports\backtests`
- `data\reports\daily`
- `data\reports\weekly`
- `data\reports\model_feedback`
- `data\exports`
- `data\emergency_logs`
- `data\backups`

Data outputs:
- `data\reports\tv_backtest_markers.pine` ← NEW 2026-05-03: generated Pine Script indicator

Logs:
- `logs\system.log`
- `logs\strategy.log`
- `logs\execution.log`

## Obsidian

- `C:\Users\m080p\iCloudDrive\iCloud~md~obsidian\15m1m\MT5 Rectangle AI System.canvas`

## MT5 Files

Terminal data path:

`C:\Users\m080p\AppData\Roaming\MetaQuotes\Terminal\930119AA53207C8778B41171FBFFB46F`

Files:
- `MQL5\Indicators\RectangleBacktestMarkers.mq5`
- `MQL5\Indicators\RectangleBacktestMarkers.ex5`
- `MQL5\Files\GBPUSD_rectangle_backtest_trades.csv`

## 2026-05-05 Vision Redesign Additions/Updates

Root:

- `C:\15m-1m\mt5_rectangle_ai\config.yaml` updated: simplified vision-gate config, removed EMA/imbalance/session config, added Claude model/min confidence.
- `C:\15m-1m\mt5_rectangle_ai\requirements.txt` updated: added `mplfinance`.

Core:

- `core\chart_renderer.py` new: renders 60-candle M15 sweep chart PNG for Claude vision.
- `core\config_loader.py` updated: loads simplified `RuleEngineConfig`.

Strategy:

- `strategy\structure_detector.py` simplified: no clean-structure/min-distance gate; level invalidated only by close through.
- `strategy\sweep_detector.py` simplified: wick through + close back + candle colour only.
- `strategy\skip_reasons.py` updated: added `SKIP_WRONG_CANDLE_COLOUR`.
- `strategy\state_machine.py` updated: bypasses EMA/imbalance/session modules and includes Claude vision gate.
- `strategy\state_machine.py` updated: corrected M1 monitoring to start at `M15 trigger_time + 15 minutes`, inclusive.
- `strategy\signal_builder.py` updated: simplified setup object and added `vision_review`.

AI:

- `ai\vision_client.py` new: sends chart image to Claude and parses JSON approval.
- `ai\vision_client.py` updated: quality-checker prompt v2.

Backtesting:

- `backtesting\mechanical_backtest.py` updated: calls `scan_m15(..., use_vision=False)` and auto-approves mechanical backtests.

Generated outputs:

- `C:\15m-1m\mt5_rectangle_ai\vision_test_GBPUSD.png`
- `C:\15m-1m\mt5_rectangle_ai\vision_confidence_breakdown_GBPUSD_v2.csv`
- `C:\15m-1m\mt5_rectangle_ai\vision_charts\*.png`

## 2026-05-06 Updates

Config:

- `C:\15m-1m\mt5_rectangle_ai\config.yaml`
  - `m1_flip.max_wait_candles` changed to `0` for unlimited M1 wait.
  - `sl.buffer_points.forex` changed to `0` so GBPUSD SL sits exactly on rectangle edge.

Core/strategy/backtesting:

- `core\candle_builder.py`
  - Current checked state still uses `datetime.fromtimestamp(value_time)` for numeric timestamps; UTC conversion was discussed but not applied in the last interrupted turn.
- `strategy\m1_flip.py`
  - `M1FlipConfig.max_wait_candles` default changed to `0`.
  - `detect_m1_flip` treats `0` as unlimited.
  - Timeout skip only applies when `max_wait_candles > 0`.
- `strategy\state_machine.py`
  - Chart output folder can be overridden with `VISION_CHARTS_DIR`.
- `backtesting\mechanical_backtest.py`
  - M1 candles for entry now start at M15 close (`candle.time + 15 minutes`).
  - Added `rectangle_low` and `rectangle_high` fields to trade CSV output.
  - Added `--sl-buffer-points`, `--end-time`, and `--use-vision` CLI options.
  - Vision-enabled backtests now store Claude confidence in `ai_score`.
- `backtesting\generate_tv_indicator.py`
  - Reads stored rectangle bounds instead of reconstructing them.
  - Uses newest compatible CSV by modified time.
  - Skips open trades without exit timestamps.
  - Handles BOM CSVs with `utf-8-sig`.

Generated outputs:

- `C:\15m-1m\mt5_rectangle_ai\data\reports\backtests\GBPUSD_no_buffer_plus8R_trades.csv`
- `C:\15m-1m\mt5_rectangle_ai\data\reports\backtests\GBPUSD_no_buffer_plus8R_summary.json`
- `C:\15m-1m\mt5_rectangle_ai\data\reports\backtests\GBPUSD_20260506_004151_trades.csv`
- `C:\15m-1m\mt5_rectangle_ai\data\reports\backtests\GBPUSD_20260506_004151_summary.json`
- `C:\15m-1m\mt5_rectangle_ai\data\reports\backtests\GBPUSD_20260506_005041_trades.csv`
- `C:\15m-1m\mt5_rectangle_ai\data\reports\backtests\GBPUSD_20260506_005041_summary.json`
- `C:\15m-1m\mt5_rectangle_ai\vision_charts_claude_20260506_vision_test\*.png`
- `C:\15m-1m\mt5_rectangle_ai\data\reports\tv_backtest_markers.pine` regenerated from latest Claude vision run.

## 2026-05-06 Part 2: Recovery System + Historical Data Infrastructure

### Recovery folder (new, isolated from live system)

- `C:\15m-1m\Recovery\GBPUSD_no_buffer_plus8R_trades.csv` — copy of original +8R trade list (40 trades, 12W/28L)
- `C:\15m-1m\Recovery\GBPUSD_no_buffer_plus8R_summary.json` — summary with UTC+5 timestamp caveat
- `C:\15m-1m\Recovery\mechanical_backtest_plus8R.py` — recovery backtest snapshot:
  - `end_time = datetime.now()` (NOT utcnow — machine local UTC+2)
  - points to old MCP server via `_OLD_MCP_CONFIG`
  - has same MA filter, BE, --data-dir features as production
- `C:\15m-1m\Recovery\mt5_mcp_server_old.py` — old MCP server snapshot:
  - uses `datetime.fromtimestamp(r["time"])` (adds machine UTC+2 offset)
  - server name `"mt5-fusion-markets-old"`
  - no `_BROKER_OFFSET` constant
  - does NOT have `pos` parameter in `get_candles` (pre-chunk-fetch)

### Production backtest (updated)

- `C:\15m-1m\mt5_rectangle_ai\backtesting\mechanical_backtest.py`
  - Added MA trend filter (`--ma-period`, default 60; 0 = disabled)
  - Added breakeven logic (`--breakeven-r`, default 2.0; 0 = disabled)
  - Added `--data-dir` for offline cached data
  - Added `LocalDataEngine` import

### Historical data infrastructure (new)

- `C:\15m-1m\mt5_rectangle_ai\backtesting\fetch_historical.py`
  - Fetches M15 + M1 candles from MT5 in 50,000-bar chunks
  - Saves `{TF}.csv` + `symbol_info.json` per symbol
  - Handles MT5 history limit gracefully (try/except on chunk calls)
- `C:\15m-1m\mt5_rectangle_ai\core\local_data_engine.py`
  - Drop-in replacement for `Mt5DataEngine`
  - Reads from pre-fetched CSVs; ignores `count` (returns full dataset)
  - Same interface: `get_candles()`, `symbol_info()`, `latest_closed_m15()`, `m1_after()`

### MCP server (updated)

- `C:\mt5-mcp\mt5_mcp_server.py`
  - Added `pos` parameter (default 0) to `get_candles` tool handler
  - Enables chunked M1 fetching: `mt5.copy_rates_from_pos(symbol, tf, pos, count)`

### Cached historical data (new data files)

- `C:\15m-1m\mt5_rectangle_ai\data\historical\EURUSD\M15.csv` — 9,640 bars (2025-12-15 to 2026-05-06)
- `C:\15m-1m\mt5_rectangle_ai\data\historical\EURUSD\M1.csv` — 100,000 bars (2026-01-29 to 2026-05-06)
- `C:\15m-1m\mt5_rectangle_ai\data\historical\EURUSD\symbol_info.json`
- `C:\15m-1m\mt5_rectangle_ai\data\historical\NAS100\M15.csv` — 9,640 bars (2025-12-08 to 2026-05-06)
- `C:\15m-1m\mt5_rectangle_ai\data\historical\NAS100\M1.csv` — 100,000 bars (2026-01-23 to 2026-05-06)
- `C:\15m-1m\mt5_rectangle_ai\data\historical\NAS100\symbol_info.json`
