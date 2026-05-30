# 15m-1m Project Memory

Date written: 2026-05-04 (updated from 2026-05-03 session)

## Goal

Build a local MT5/Fusion Markets trading research system for the M15/M1 rectangle strategy from the PDF:

- M15 identifies the directional setup.
- M15 weakness sweep creates the rectangle.
- M1 close outside the rectangle confirms entry.
- SL/TP and journal state are deterministic.
- AI may score only after a mechanically valid setup; AI must not control rule logic.

## Source Documents Read

- `C:\Users\m080p\Downloads\15m-1m.pdf`
- `C:\15m-1m\Technical Blueprint — Version 0.1.txt`
- `C:\15m-1m\Rule Engine Specification — V0.1.txt`
- `C:\15m-1m\Journal + Database Specification — V0.1.txt`

## Project Scaffold

Created project at:

`C:\15m-1m\mt5_rectangle_ai`

## Rule Engine Built

Implemented deterministic Phase 1 strategy modules:

- `core/candle_builder.py`
- `strategy/ema_filter.py`
- `strategy/structure_detector.py`
- `strategy/imbalance_detector.py`
- `strategy/session_levels.py`
- `strategy/sweep_detector.py`
- `strategy/rectangle.py`
- `strategy/m1_flip.py`
- `strategy/signal_builder.py`
- `strategy/state_machine.py`
- `strategy/skip_reasons.py`

## MT5 MCP Integration

MT5 MCP server path:

`C:\mt5-mcp\mt5_mcp_server.py`

The server is stdio MCP and exposes tools including:

- `get_account`, `get_price`, `get_positions`, `place_order`
- `get_candles`, `get_symbols`, `symbol_info`, `risk_check`

Important caveat:

- `drop_current=True` is good during open markets, but can hide the latest already-closed bar when markets are closed.

## Per-Symbol Config System (added 2026-05-03)

Root cause discovered: all `points` thresholds in config.yaml were calibrated for forex (point=0.00001) but NAS100 and XAUUSD have point=0.01. This caused every NAS100/XAUUSD sweep to be rejected as "too deep" (e.g. a 10-point NAS100 sweep = 10/0.01 = 1000 raw points, exceeding max_sweep_depth_points=150).

Fix:

- `config.yaml` updated: sweep/rectangle/ema/structure thresholds now support per-category dicts (forex/metals/indices/default) — same pattern as existing `sl.buffer_points`.
- `core/config_loader.py` created: reads config.yaml and resolves the correct values for any symbol using `get_symbol_setting`.
- `backtesting/mechanical_backtest.py` updated: calls `load_rule_engine_config(symbol)` and passes it to `SymbolRuleState`.

Key confirmed values (2026-05-03, MT5 live data):

- NAS100: point=0.01, digits=2, price ~27,700
- XAUUSD: point=0.01, digits=2, price ~4,614
- EURUSD: point=0.00001, digits=5, price ~1.1720
- Symbol name "NAS100" confirmed correct on Fusion Markets MT5 (was "US100" in old config — fixed)

Current per-category thresholds in config.yaml:

```
sweep.max_sweep_depth_points:  forex=150 (15 pips), metals=5000 ($50), indices=10000 (100 NAS pts)
sweep.min_sweep_depth_points:  forex=5,             metals=200 ($2),   indices=200 (2 NAS pts)
rectangle.max_size_points:     forex=100 (10 pips),  metals=3000 ($30),  indices=5000 (50 NAS pts)
rectangle.min_size_points:     forex=5,             metals=1000 ($10),  indices=2000 (20 NAS pts)
ema.min_distance_from_ema:     forex=20,            metals=500 ($5),   indices=1000 (10 NAS pts)
sl.buffer_points:              forex=2,             metals=20 ($0.2),  indices=50 (0.5 NAS pts)
```

Open issue: SL buffer for indices (50 raw pts = 0.5 NAS pts) and metals (20 raw pts = $0.20) are still too small — user flagged SL as "hugging". Fix pending — waiting for user to first review trades visually on TradingView indicator.

## Journal + Database Built

Upgraded journal/database to V0.1 spec. Main file: `journal/journal.py`. Schema: `journal/schema.sql`.

Tables: setups, ai_reviews, m1_events, trades, trade_events, screenshots, daily_stats, system_events. View: ai_training_view.

## Backtesting

Runner: `backtesting/mechanical_backtest.py`

Command pattern:
```powershell
python -m backtesting.mechanical_backtest --symbol NAS100 --days 14
```

See BACKTEST_RESULTS.md for current results.

## MT5 Chart Markers Indicator

MCP cannot draw chart objects directly. Created custom MT5 indicator.

Terminal data folder:

`C:\Users\m080p\AppData\Roaming\MetaQuotes\Terminal\930119AA53207C8778B41171FBFFB46F`

Files:
- `MQL5\Indicators\RectangleBacktestMarkers.mq5`
- `MQL5\Indicators\RectangleBacktestMarkers.ex5`
- `MQL5\Files\GBPUSD_rectangle_backtest_trades.csv`

CSV uses Unix timestamps. Vertical lines removed. User confirmed markers visible.

## TradingView Pine Script Indicator (added 2026-05-03)

Created Python generator that reads backtest CSVs and produces a Pine Script indicator.

Generator: `backtesting/generate_tv_indicator.py`

Output: `data/reports/tv_backtest_markers.pine`

Run command:
```powershell
python -m backtesting.generate_tv_indicator
```

Indicator features:
- Draws for all 3 symbols (EURUSD, GBPUSD, NAS100) — auto-detects from syminfo.tickerid
- Shaded rectangle box from setup candle → trade exit (sweep zone)
- Entry label "▲ ENTRY / ▼ ENTRY" at entry price
- Exit label "✔ +3R / ✘ -1R" at TP or SL price level
- Dashed SL line (red) and TP line (green)
- Uses xloc.bar_time so works on any timeframe

Must be on M15 and scrolled to April 20–30 to see trades. Symbol name in TradingView must contain "EURUSD", "GBPUSD" or "NAS100".

Open issue: user reports rectangle box not sitting on sweep wick and no entry/exit labels visible. Awaiting user confirmation of (a) timeframe, (b) scroll position, (c) exact TV symbol name.

## Obsidian Canvas

`C:\Users\m080p\iCloudDrive\iCloud~md~obsidian\15m1m\MT5 Rectangle AI System.canvas`

## Important Commands That Passed

- `python -m compileall C:\15m-1m\mt5_rectangle_ai`
- `python C:\15m-1m\mt5_rectangle_ai\main.py`
- MCP `get_account` smoke test.
- MCP candle fetches for NAS100, EURUSD, GBPUSD, XAUUSD confirmed working.
- `python -m backtesting.mechanical_backtest --symbol NAS100 --days 14` (now produces results)
- `python -m backtesting.generate_tv_indicator`

## Current State

Working:
- project scaffold.
- deterministic rule engine.
- MT5 MCP read integration.
- per-symbol config loader.
- journal/database V0.1.
- mechanical backtest runner (all 4 symbols now producing results).
- GBPUSD MT5 marker indicator.
- TradingView Pine Script indicator (pending visual confirmation).
- Obsidian system canvas.

Not yet built:
- long-running daemon loop.
- persistent MCP session optimization.
- Claude API real integration.
- live/paper execution loop.
- robust spread/commission/slippage backtest.
- true candle-close scheduler.
- news filter.
- kill switch implementation.
- dashboard UI.
- SL buffer fix for indices/metals (pending TV indicator review).

## 2026-05-05 Update: Vision-Based AI Gate Redesign

Project root remains:

`C:\15m-1m\mt5_rectangle_ai`

Architecture changed to:

- M15 candle closes.
- Find recent pivot swing high/low.
- Detect weakness sweep mechanically.
- Render M15 chart image from candles.
- Send rendered image to Claude vision for quality approval/rejection.
- If approved, watch M1 for close outside rectangle.
- Entry/SL/TP remain deterministic.

Important M15/M1 timing correction:

- MT5 candle timestamps are bar open times.
- An M15 candle stamped `13:15` closes at `13:30`.
- M1 monitoring now starts at first M1 bar with `time >= trigger_time + 15 minutes`.
- For GBPUSD `2026-05-05T13:15:00` short, first eligible M1 bar is `13:30`; first close below rectangle in MT5 data was `13:33`.

Mechanical simplifications:

- `strategy/sweep_detector.py` checks only wick through, close back inside, and correct candle colour.
- `strategy/skip_reasons.py` added `SKIP_WRONG_CANDLE_COLOUR`.
- `strategy/structure_detector.py` returns the most recent swing pivot within age that has not been closed through.
- `level_already_swept` invalidates only by close beyond level, not wick.
- Clean-structure and min-swing-distance gates were removed from active structure logic.
- EMA, imbalance, and session modules still exist but are bypassed in `strategy/state_machine.py`.

Vision additions:

- `core/chart_renderer.py` renders last 60 M15 candles with mplfinance.
- `ai/vision_client.py` sends PNG chart to Claude model `claude-sonnet-4-6`.
- `requirements.txt` includes `mplfinance`.
- `config.yaml` simplified and includes `ai.model: claude-sonnet-4-6`, `ai.min_confidence: 60`.

Claude quality-checker prompt v2:

- Claude is told not to re-check mechanics because the system already confirmed them.
- Claude should assess visual quality only:
  - clear swing level.
  - proportionate sweep candle.
  - visible/tradeable rectangle.
  - price moved toward the level, not choppy sideways around it.
- Reject random/mid-range levels, huge spike candles, thin rectangles, choppy repeated tests, or repeated prior wicks.
- Do not reject for general momentum, extended trend, news/fundamentals, or uncertainty about future price.

Important live vision test:

- GBPUSD M15 sweep: `2026-05-05T13:15:00`, direction short.
- Rendered image: `C:\15m-1m\mt5_rectangle_ai\vision_test_GBPUSD.png`.
- Claude approved:
  - old prompt confidence: 72.
  - v2 prompt confidence: 82.
- Corrected M1 entry after M15 close:
  - entry time `2026-05-05T13:33:00`.
  - entry price `1.35469`.
  - no-buffer SL at rectangle high `1.35505`.
  - TP `1.35361`.
  - hit TP at `2026-05-05T14:17:00`, +3R.

Backtest and Claude findings:

- Mechanical backtests now call `scan_m15(..., use_vision=False)` and auto-approve.
- Claude tests were ad-hoc scripts, not normal saved backtest reports.
- No-buffer tests used `replace(load_rule_engine_config(symbol), sl_buffer_points=0)` and did not change config.
- Full v2 Claude confidence/outcome breakdown saved to:
  `C:\15m-1m\mt5_rectangle_ai\vision_confidence_breakdown_GBPUSD_v2.csv`
- Confidence threshold is not useful:
  - trades 24, wins 6, losses 18.
  - average confidence winners 75.67.
  - average confidence losers 77.89.
  - winners >=75: 3.
  - losers >=75: 13.
- Next likely direction: few-shot prompting or a different scoring target, not simple threshold tuning.

## 2026-05-06 Update: TradingView, No-Buffer SL, M1 Wait, Claude Vision Backtest

Project root:

`C:\15m-1m\mt5_rectangle_ai`

Important current code/config state:

- `config.yaml` now has `sl.buffer_points.forex: 0`, so GBPUSD SL is exactly on the rectangle edge:
  - buy SL = `rectangle_low`.
  - sell SL = `rectangle_high`.
- `config.yaml` now has `m1_flip.max_wait_candles: 0`.
- `strategy/m1_flip.py` treats `max_wait_candles == 0` as unlimited M1 wait.
- `backtesting/mechanical_backtest.py` M1 filtering now starts at the M15 candle close:
  `bar.time >= candle.time + timedelta(minutes=15)`.
- `backtesting/mechanical_backtest.py` has CLI flags:
  - `--sl-buffer-points`
  - `--end-time`
  - `--use-vision`
- `strategy/state_machine.py` supports `VISION_CHARTS_DIR` env var to save rendered Claude charts to a chosen folder.
- `backtesting/generate_tv_indicator.py` now reads `rectangle_low`/`rectangle_high` from CSV instead of reconstructing bounds from SL/buffer/size.
- `backtesting/generate_tv_indicator.py` picks newest compatible CSV by modified time and skips open trades without `exit_time`.

Timestamp note:

- User reported TradingView alignment looked good after reruns.
- Current checked code still shows `core/candle_builder.py` using `datetime.fromtimestamp(value_time)` for numeric timestamps.
- The UTC conversion change was not applied during the last interrupted timestamp-fix turn. If timestamp drift returns, revisit this line.

Latest important files:

- Latest no-buffer mechanical result:
  `C:\15m-1m\mt5_rectangle_ai\data\reports\backtests\GBPUSD_20260506_004151_trades.csv`
  and summary JSON with 46 trades, 12 wins, 34 losses, total R `+2.0`.
- Latest Claude vision result:
  `C:\15m-1m\mt5_rectangle_ai\data\reports\backtests\GBPUSD_20260506_005041_trades.csv`
  and summary JSON with 28 approved trades, 7 wins, 21 losses, total R `0.0`.
- Latest Claude screenshots folder:
  `C:\15m-1m\mt5_rectangle_ai\vision_charts_claude_20260506_vision_test`
  containing 46 PNG screenshots.
- Latest TradingView indicator:
  `C:\15m-1m\mt5_rectangle_ai\data\reports\tv_backtest_markers.pine`
  generated from the latest Claude vision run, containing 28 GBPUSD trades.

Latest Claude vision run command:

```powershell
$env:PYTHONPATH='C:\15m-1m\mt5_rectangle_ai'
$env:VISION_CHARTS_DIR='C:\15m-1m\mt5_rectangle_ai\vision_charts_claude_20260506_vision_test'
python backtesting/mechanical_backtest.py --symbol GBPUSD --days 14 --use-vision
python backtesting/generate_tv_indicator.py
```

## 2026-05-06 Update (Part 2): Recovery System, MA Filter, BE, Historical Data Fetch

### Timezone Bug and Recovery Isolation

The +8R GBPUSD result (40 trades, 12W/28L) was produced by a system with two compounding timezone errors:

1. `backtesting/mechanical_backtest.py` used `datetime.now()` (machine local time, UTC+2) instead of `datetime.utcnow()`.
2. `C:\mt5-mcp\mt5_mcp_server.py` used `datetime.fromtimestamp(r["time"])` (adds local UTC+2 again) instead of `utcfromtimestamp() - timedelta(hours=3)` (true UTC).

Net effect: all candle timestamps were UTC+5 (broker UTC+3 + machine UTC+2). Results were internally consistent so trade outcomes are valid, but timestamps are offset from true UTC.

Recovery isolation created in `C:\15m-1m\Recovery\`:

- `mt5_mcp_server_old.py` — copy of old MCP server with `fromtimestamp()` restored. Server name `"mt5-fusion-markets-old"`. No `_BROKER_OFFSET` constant.
- `mechanical_backtest_plus8R.py` — copy of old backtest with `datetime.now()` restored. Points to old server via `_OLD_MCP_CONFIG`. Has same MA/BE/data-dir features as production.
- `GBPUSD_no_buffer_plus8R_trades.csv` — original 40-trade CSV.
- `GBPUSD_no_buffer_plus8R_summary.json` — summary with UTC+5 caveat note.

Both scripts are fully isolated. The corrected live system (`C:\mt5-mcp\mt5_mcp_server.py`) is NOT touched.

### Why +8R Cannot Be Exactly Reproduced

`copy_rates_from_pos(symbol, tf, 0, count)` returns the latest N bars at call time. The following day, new bars have been added and old bars have dropped off. Warmup history changes → different setup detections. The 12 wins were consistent across replays, but extra losing setups appeared in the new window. The original +8R was a specific moment-in-time snapshot.

### Why Corrected and Recovery Results Are Identical on 14-day Window

Both systems use the same 14 calendar days of price data. The 2-hour UTC vs UTC+2 offset does not shift which trading sessions fall inside the 14-day window at this scale. Divergence would only appear over longer runs where the boundary shifts a trade in or out.

### MA Filter

Added `--ma-period` (default 60) to both production and recovery backtest scripts.

Logic: computed from `mean(c.close for c in history[-ma_period:])` at setup detection time. Longs only when M15 close ≥ MA, shorts only when M15 close ≤ MA. Disabled with `--ma-period 0`.

### 2R Breakeven Logic

Added `--breakeven-r` (default 2.0) to both scripts.

Logic:
- `use_be = breakeven_r > 0`
- `be_trigger = entry ± risk * breakeven_r`
- `be_active = False` initially; set True when price reaches trigger
- When `be_active=True`: SL moves to entry; `hit_sl` becomes a breakeven exit (0.0R)
- Critical bug was fixed: original version had `be_active = breakeven_r <= 0`, which started all trades with BE already active when `breakeven_r=0`, turning every SL into a 0.0R breakeven. Fix: always init `be_active = False`, use separate `use_be` flag.

### Historical Data Caching System

Created two new components to decouple backtests from live MT5 calls:

**`backtesting/fetch_historical.py`**
- Fetches M15 and M1 candles from MT5 in chunks of 50,000 bars (MT5 limit is ~100,000 M1 bars total, ~70 trading days)
- Saves to `data/historical/{SYMBOL}/{TF}.csv` + `symbol_info.json`
- Exception handler wraps each chunk call so already-fetched bars are saved if MT5 history runs out

**`core/local_data_engine.py`**
- Drop-in for `Mt5DataEngine` when `--data-dir` is supplied
- Reads from pre-fetched CSVs; ignores `count` parameter (returns full dataset)
- Same interface: `get_candles()`, `symbol_info()`, `latest_closed_m15()`, `m1_after()`

**`C:\mt5-mcp\mt5_mcp_server.py`** edited:
- Added `pos` parameter (default 0) to `get_candles` handler for chunked fetching
- `rates = mt5.copy_rates_from_pos(symbol, TIMEFRAMES[tf_str], pos, count)`

Data fetched and saved:
- `C:\15m-1m\mt5_rectangle_ai\data\historical\EURUSD\M15.csv` — 9,640 bars (2025-12-15 to 2026-05-06)
- `C:\15m-1m\mt5_rectangle_ai\data\historical\EURUSD\M1.csv` — 100,000 bars (2026-01-29 to 2026-05-06)
- `C:\15m-1m\mt5_rectangle_ai\data\historical\NAS100\M15.csv` — 9,640 bars (2025-12-08 to 2026-05-06)
- `C:\15m-1m\mt5_rectangle_ai\data\historical\NAS100\M1.csv` — 100,000 bars (2026-01-23 to 2026-05-06)

Run command:
```powershell
$env:PYTHONPATH = "C:\15m-1m\mt5_rectangle_ai"
cd C:\15m-1m\mt5_rectangle_ai
python backtesting/fetch_historical.py --symbols EURUSD NAS100 --days 90
```

Run backtest on cached data:
```powershell
python backtesting/mechanical_backtest.py --symbol NAS100 --days 90 --data-dir "C:\15m-1m\mt5_rectangle_ai\data\historical" --ma-period 0 --breakeven-r 2.0
```
