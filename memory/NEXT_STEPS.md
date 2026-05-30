# Recommended Next Steps

## IMMEDIATE — In Progress

### A. Confirm TradingView Indicator Working
User is testing `data/reports/tv_backtest_markers.pine` on TradingView web.
Issues pending resolution:
- Rectangle box needs to align with sweep candle wick (user reports it's "floating")
- Entry/exit labels not visible
- Need user to confirm: (1) M15 timeframe, (2) scrolled to April 20–30, (3) exact TV symbol name
- Last version sent extends box from setup candle to exit time — waiting for feedback

### B. Fix SL Buffer + Min Rectangle Size
User flagged SL as "hugging" entry. Planned changes (pending TV indicator visual review first):
- `sl.buffer_points` for indices: 50 → 500 (5 NAS100 price units)
- `sl.buffer_points` for metals: 20 → 200 (2 XAUUSD price units)
- `rectangle.min_size_points` for indices: 2000 → keep or increase (20 NAS pts min)
- After fix: re-run all 4 symbol backtests and regenerate TV indicator

## 1. Improve Backtesting

Add:
- spread.
- commission.
- slippage.
- bid/ask simulation.
- session filters.
- skip reason counts saved in summary.
- option to run all configured symbols in one command.

## 2. Backtest Reporting

Add reports:
- setups by skip reason.
- trades by session.
- rectangle size vs result.
- sweep depth vs result.
- wick ratio vs result.

## 3. Journal Backtest Runs

Add one of:
- separate `backtest_runs` table.
- or write setups/trades to journal with `mode = backtest`.

Current journal schema does not have a `mode` field.

## 4. Claude Phase 2

Build actual Claude API integration:
- prompt setup object.
- parse JSON response.
- write `ai_reviews`.
- apply threshold gate.
- compare AI-approved vs all-mechanical backtest.

## 5. Daemon Loop

Build scheduler:
- poll only at M15 close.
- maintain per-symbol `SymbolRuleState`.
- activate M1 monitoring only after rectangle.
- log every lifecycle state.

## 6. Safety Before Execution

Before demo/paper order sending:
- kill switch file.
- no-order mode default.
- daily loss lock.
- max trades/day lock.
- max one symbol initially.
- spread block.
- position conflict block.

## 7. MT5 MCP Server Upgrade (optional)

Add MCP tools for chart objects (draw arrow, line, rectangle, screenshot). Would remove need for CSV + indicator workaround.

## 2026-05-05 Updated Priorities

### 1. Few-Shot Claude Vision Prompt

Confidence threshold testing showed threshold is not useful:

- v2 Claude quality prompt, GBPUSD no-buffer, 14-day rerun.
- Trades: 24.
- Wins: 6.
- Losses: 18.
- Avg confidence winners: 75.67.
- Avg confidence losers: 77.89.
- Losers >= 75 confidence: 13.

Next step:

- Build few-shot visual examples or richer prompt criteria.
- Include examples of rejected high-confidence losers and approved winners.
- Target actual failure modes instead of raising `ai.min_confidence`.

### 2. Persist Claude Vision Test Runs

Current Claude vision backtests were ad-hoc scripts. Need proper persistence:

- Save every Claude review with setup_id, image path, approved, confidence, reason.
- Save every trade outcome tied to review.
- Save summary JSON/CSV per run.
- Cache image/review by setup_id + prompt version to avoid repeated paid calls.

### 3. Decide SL Buffer Policy

No-buffer GBPUSD mechanical run improved:

- Config-buffer run: total R +1.0.
- No-buffer run: total R +8.0.
- Specific `2026-05-05T13:15` short became +3R with SL at rectangle high.

Need decide whether to:

- set forex `sl.buffer_points` to 0.
- keep buffer in live execution for spread/bid-ask safety.
- model spread/commission first before changing config.

### 4. TradingView Indicator

Latest TradingView indicator may not reflect post-redesign/no-buffer/Claude-filtered results. Regenerate only after choosing intended result set:

- mechanical config-buffer.
- mechanical no-buffer.
- Claude v2 filtered no-buffer.

## 2026-05-06 Part 2: Current Priorities

### 1. NAS100 Is the Promising Symbol — Investigate Further

90-day results show NAS100 is naturally +15R with no filters, +18R with BE@2R alone.
The 60 MA filter is actively harmful for NAS100. EURUSD is deeply negative.

Recommended next experiments (all can use cached --data-dir without hitting MT5):

- Test shorter MA periods (20, 200) on NAS100 to see if any MA period is helpful or all hurt
- Test BE at different R levels (1.5, 3.0) on NAS100 no-MA
- Investigate what kinds of setups are winning vs losing (direction, time of day, rectangle size)
- Consider running the same tests on GBPUSD which showed +8R on a shorter window

Run command pattern:
```powershell
$env:PYTHONPATH = "C:\15m-1m\mt5_rectangle_ai"
python backtesting/mechanical_backtest.py --symbol NAS100 --days 90 --data-dir "C:\15m-1m\mt5_rectangle_ai\data\historical" --ma-period 0 --breakeven-r 2.0
```

### 2. Fetch GBPUSD Historical Data

GBPUSD was the original +8R symbol but we only have EURUSD and NAS100 cached.

```powershell
python backtesting/fetch_historical.py --symbols GBPUSD --days 90
```

Then run a 90-day GBPUSD comparison with no MA and BE@2R.

### 3. Understand Why NAS100 Works But EURUSD Doesn't

Key question: is EURUSD structural (strategy doesn't fit the instrument/volatility) or is it the Feb–May 2026 window (tariff-driven trends that don't suit mean-reversion setups)?

Test: run EURUSD on a different 90-day window once older data is available, or compare against a calmer forex period.

### 4. Review Latest Claude Screenshots

Latest Claude vision run saved all mechanical setup screenshots to:

`C:\15m-1m\mt5_rectangle_ai\vision_charts_claude_20260506_vision_test`

There are 46 PNGs. Claude approved 28 trades, but result was breakeven (`0.0R`), so next useful step is visual review of:

- approved losers.
- rejected winners if a rejected-setups report is added.
- low-quality charts where Claude still approved.

### 5. Persist All Claude Reviews, Not Just Approved Trades

Current saved trade CSV contains only approved trades that reached entry. It does not save rejected Claude reviews in a structured CSV.

Add a proper vision-run report with:

- setup_id.
- setup_time.
- image_path.
- approved/rejected.
- confidence.
- reason.
- whether M1 entry occurred.
- outcome when applicable.

### 6. Fix/Confirm Timestamp Normalization

User reported TradingView boxes now align, but current checked code still has:

`core/candle_builder.py: datetime.fromtimestamp(value_time)`

If any time drift appears again, change numeric timestamp parsing to UTC consistently and rerun backtests/indicator.

### 7. Keep SL Buffer Policy Explicit

Current config sets forex SL buffer to `0`, meaning SL is exactly at rectangle edge. This matched the user request and was verified in latest mechanical/Claude runs.

Before live/paper execution, decide whether to:

- keep exact rectangle-edge SL.
- add bid/ask/spread modeling instead of fixed SL buffer.
- add live execution spread safety separately from backtest geometry.
