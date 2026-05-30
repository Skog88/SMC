# Backtest Results Memory

## Run 1 — Original (2026-05-02/03, broken config)

NAS100/XAUUSD had 0 setups due to point-scaling bug. GBPUSD had 5 trades but one ghost run file (_235458) with 0 bars. Use _235602 file for valid GBPUSD results.

## Run 2 — Fixed Config (2026-05-03, corrected thresholds)

Run date: 2026-05-03

Backtest runner: `C:\15m-1m\mt5_rectangle_ai\backtesting\mechanical_backtest.py`

Command pattern:
```powershell
cd C:\15m-1m\mt5_rectangle_ai
python -m backtesting.mechanical_backtest --symbol NAS100 --days 14
```

### Method

Mechanical-only Phase 1:
- Fetch M15 and M1 candles from MT5 MCP.
- Run deterministic rule engine with per-symbol config.
- Auto-approve instead of Claude.
- Wait for M1 flip.
- Simulate SL/TP on later M1 candles.
- TP fixed at 3R, SL fixed at 1R.
- Same-candle TP/SL ambiguity → count SL first.

### Results (14-day window: 2026-04-19 to 2026-05-03)

#### NAS100
- M15 bars: 920 | M1 bars: 13,790
- Setups: 5 | Trades: 5
- Wins: 3 | Losses: 2
- Win rate: 60.0%
- Total R: +7.0 | Average R: +1.4

NAS100 trades:
| Setup Time | Entry Time | Dir | Entry | SL | TP | Exit | Reason | R |
|---|---|---|---:|---:|---:|---|---|---:|
| 2026-04-20T16:00 | 2026-04-20T16:15 | buy | 26568.20 | 26543.20 | 26643.20 | 2026-04-20T18:08 | TP_HIT | +3.0 |
| 2026-04-21T05:30 | 2026-04-21T05:42 | buy | 26667.18 | 26651.56 | 26714.04 | 2026-04-21T11:08 | TP_HIT | +3.0 |
| 2026-04-21T17:15 | 2026-04-21T17:30 | buy | 26727.86 | 26693.86 | 26829.86 | 2026-04-21T17:38 | SL_HIT | -1.0 |
| 2026-04-22T09:00 | 2026-04-22T09:04 | buy | 26682.35 | 26668.48 | 26723.96 | 2026-04-22T09:21 | SL_HIT | -1.0 |
| 2026-04-24T14:15 | 2026-04-24T14:16 | buy | 26974.82 | 26938.69 | 27083.21 | 2026-04-24T16:04 | TP_HIT | +3.0 |

Note: SL distances for NAS100 trades 3 and 4 (13–34 NAS pts) are tight. User flagged SL as "hugging". Fix pending (increase sl_buffer_points for indices and min_size_points).

#### EURUSD
- M15 bars: 960 | M1 bars: 14,318
- Setups: 5 | Trades: 4
- Wins: 0 | Losses: 4
- Win rate: 0.0%
- Total R: -4.0 | Average R: -1.0

EURUSD trades (all SL_HIT):
| Setup Time | Entry Time | Dir | Entry | SL | TP | Exit | R |
|---|---|---|---:|---:|---:|---|---:|
| 2026-04-20T19:45 | 2026-04-20T19:46 | buy | 1.17769 | 1.17623 | 1.18207 | 2026-04-21T13:05 | -1.0 |
| 2026-04-28T17:45 | 2026-04-28T17:46 | sell | 1.16963 | 1.17001 | 1.16849 | 2026-04-28T18:35 | -1.0 |
| 2026-04-29T20:45 | 2026-04-29T20:53 | sell | 1.16903 | 1.17044 | 1.16480 | 2026-04-30T15:29 | -1.0 |
| 2026-04-30T11:00 | 2026-04-30T11:01 | sell | 1.16604 | 1.16655 | 1.16451 | 2026-04-30T11:26 | -1.0 |

#### GBPUSD
- M15 bars: 960 | M1 bars: 14,353
- Setups: 2 | Trades: 2
- Wins: 1 | Losses: 1
- Win rate: 50.0%
- Total R: +2.0 | Average R: +1.0

GBPUSD trades:
| Setup Time | Entry Time | Dir | Entry | SL | TP | Exit | Reason | R |
|---|---|---|---:|---:|---:|---|---|---:|
| 2026-04-23T02:45 | 2026-04-23T02:58 | sell | 1.35035 | 1.35097 | 1.34849 | 2026-04-23T05:15 | TP_HIT | +3.0 |
| 2026-04-30T02:00 | 2026-04-30T02:03 | sell | 1.34747 | 1.34816 | 1.34540 | 2026-04-30T03:27 | SL_HIT | -1.0 |

#### XAUUSD
- M15 bars: 920 | M1 bars: 13,788
- Setups: 0 | Trades: 0
- Total R: 0

XAUUSD 0 setups is a market-condition result, not a bug. Debug confirmed 314 bars passed EMA+structure checks but none produced a qualifying sweep candle. Gold (~$4,614) did not create weakness sweeps in this 14-day window.

### Caveats

This run does not include:
- spread, commission, slippage.
- AI filter (auto-approved all setups).
- trade-session restrictions, news filter.
- exact bid/ask simulation.

Treat as a mechanical rule-engine smoke test only.

## 2026-05-05 Vision-Gate Redesign Results

These runs use the simplified M15 sweep architecture:

- structure: latest valid pivot not closed through.
- sweep: wick through + close back inside + correct candle colour.
- M1 entry starts only after M15 close (`M1.time >= M15.time + 15 minutes`).
- TP fixed at 3R.
- No spread, commission, slippage, or bid/ask simulation.

### Mechanical Auto-Approve, Config SL Buffer

GBPUSD:

- Window: 2026-04-21 to 2026-05-05.
- Setups: 44.
- Trades: 40.
- Wins: 10.
- Losses: 29.
- Open at end: 1.
- Total R: +1.0.
- Average R: +0.025.

EURUSD:

- Window: 2026-04-21 to 2026-05-05.
- Setups: 59.
- Trades: 59.
- Wins: 9.
- Losses: 50.
- Total R: -23.0.
- Average R: -0.3898.

Corrected GBPUSD `2026-05-05T13:15:00` short with config buffer:

- Entry: `2026-05-05T13:33:00`.
- Entry price: 1.35469.
- SL: 1.35530.
- TP: 1.35286.
- Result: open at end in that run.

### Mechanical Auto-Approve, No SL Buffer Override

One-off GBPUSD test using `sl_buffer_points=0`; config was not changed.

- Window: 2026-04-21 to 2026-05-05.
- Setups: 44.
- Trades: 40.
- Wins: 12.
- Losses: 28.
- Open at end: 0.
- Win rate: 30.0%.
- Total R: +8.0.
- Average R: +0.2.

Specific GBPUSD `2026-05-05T13:15:00` short:

- Entry: `2026-05-05T13:33:00`.
- Entry price: 1.35469.
- No-buffer SL: 1.35505.
- TP: 1.35361.
- Exit: `2026-05-05T14:17:00`.
- Result: TP_HIT, +3R.

### Claude Vision Enabled, Old Prompt, No SL Buffer

GBPUSD 14-day no-buffer test with Claude vision on every mechanical setup:

- Claude approved: 18.
- Claude rejected: 26.
- Approved but no M1 entry: 3.
- Trades: 15.
- Wins: 3.
- Losses: 12.
- Total R: -3.0.
- Average R: -0.2.

### Claude Vision Enabled, Quality-Checker Prompt v2, No SL Buffer

GBPUSD 14-day no-buffer test with updated quality-checker prompt:

- First v2 run: approved 25, rejected 19, trades 22, wins 5, losses 17, total R -2.0.
- Full confidence-breakdown rerun saved to:
  `C:\15m-1m\mt5_rectangle_ai\vision_confidence_breakdown_GBPUSD_v2.csv`
- Rerun: trades 24, wins 6, losses 18, rejected 18, approved no-entry 2.
- Avg confidence winners: 75.67.
- Avg confidence losers: 77.89.
- Winners >=75: 3.
- Losers >=75: 13.

Conclusion:

- Confidence threshold is not the fix.
- Losers are more concentrated above 75 confidence than winners.
- Need few-shot prompt/examples or a different scoring target.

## 2026-05-06 Results After M1/SL/TradingView Updates

### Recreated Mechanical No-Buffer +8R Run

Command:

```powershell
python -m backtesting.mechanical_backtest --symbol GBPUSD --days 14 --sl-buffer-points 0 --end-time 2026-05-05T15:05:00
```

Saved descriptive copies:

- `C:\15m-1m\mt5_rectangle_ai\data\reports\backtests\GBPUSD_no_buffer_plus8R_trades.csv`
- `C:\15m-1m\mt5_rectangle_ai\data\reports\backtests\GBPUSD_no_buffer_plus8R_summary.json`

Result:

- Setups: 44.
- Trades: 40.
- Wins: 12.
- Losses: 28.
- Open at end: 0.
- Total R: +8.0.
- Average R: +0.2.

### Mechanical, M1 Close Start Fixed, Unlimited M1 Wait, Config SL Buffer

After `m1_flip.max_wait_candles: 0` and M1 scan starts at M15 close:

- File: `GBPUSD_20260505_233635_trades.csv`.
- Setups: 46.
- Trades: 45.
- Wins: 10.
- Losses: 34.
- Open at end: 1.
- Total R: -4.0.
- Timing audit: 0 entries before M15 close.
- Note: entries can be any later M1 close, not necessarily `:00/:15/:30/:45`.

### Mechanical, Forex SL Buffer Set To 0

After `config.yaml` changed `sl.buffer_points.forex` to `0`:

- File: `GBPUSD_20260506_004151_trades.csv`.
- Setups: 46.
- Trades: 46.
- Wins: 12.
- Losses: 34.
- Open at end: 0.
- Total R: +2.0.
- Verification: `sl_not_on_rectangle_edge = 0`.

## 2026-05-06 Part 2: 90-Day Cached Data Runs (EURUSD + NAS100)

Data source: `C:\15m-1m\mt5_rectangle_ai\data\historical`
Window: ~2026-02-05 to 2026-05-06 (90 days, M1 data available from late January)
Backtest: corrected system (`mechanical_backtest.py`, `datetime.utcnow()`, true UTC candle times)

Command pattern:
```powershell
$env:PYTHONPATH = "C:\15m-1m\mt5_rectangle_ai"
python backtesting/mechanical_backtest.py --symbol EURUSD --days 90 --data-dir "C:\15m-1m\mt5_rectangle_ai\data\historical" --ma-period 60 --breakeven-r 2.0
```

### Results Table

| Symbol | MA   | BE  | Trades | W   | L   | BE  | WR%  | Total R |
|--------|------|-----|--------|-----|-----|-----|------|---------|
| EURUSD | off  | off | 348    | 70  | 277 | 0   | 20.2 | -67R    |
| EURUSD | 60   | off | 114    | 22  | 81  | 0   | 19.3 | -15R    |
| EURUSD | 60   | 2R  | 114    | 22  | 81  | 11  | 19.3 | -15R    |
| NAS100 | off  | off | 333    | 87  | 246 | 0   | 26.1 | +15R    |
| NAS100 | off  | 2R  | 333    | 77  | 213 | 43  | 23.1 | +18R    |
| NAS100 | 60   | off | 124    | 28  | 96  | 0   | 22.6 | -12R    |
| NAS100 | 60   | 2R  | 124    | 24  | 85  | 15  | 19.4 | -13R    |

### Key Findings

1. **NAS100 raw (no MA, no BE) is naturally +15R** over this 90-day window (Feb–May 2026 tariff crash + recovery period).
2. **Adding BE@2R alone on NAS100 improves to +18R** — 43 SL hits converted to 0R breakevens. Useful for drawdown reduction with no win-rate cost.
3. **MA60 filter destroys NAS100** — cuts 333 trades to 124, but the filtered subset performs at -12R. The MA filtered OUT the good setups during a strong directional trend period. The 60 MA is not appropriate for NAS100 in trending market conditions.
4. **EURUSD is deeply negative** under all configurations. The MA filter reduces exposure from 348 to 114 trades, cutting losses from -67R to -15R, but doesn't make the strategy profitable for this symbol in this window.
5. BE and MA are independent effects: on EURUSD, MA reduces trade count but BE adds minimal extra value because most trades still lose before reaching 2R in favour.

### Claude Vision Enabled, New Screenshot Folder, No Forex SL Buffer

Command used:

```powershell
$env:PYTHONPATH='C:\15m-1m\mt5_rectangle_ai'
$env:VISION_CHARTS_DIR='C:\15m-1m\mt5_rectangle_ai\vision_charts_claude_20260506_vision_test'
python backtesting/mechanical_backtest.py --symbol GBPUSD --days 14 --use-vision
```

Saved outputs:

- `C:\15m-1m\mt5_rectangle_ai\data\reports\backtests\GBPUSD_20260506_005041_trades.csv`
- `C:\15m-1m\mt5_rectangle_ai\data\reports\backtests\GBPUSD_20260506_005041_summary.json`
- `C:\15m-1m\mt5_rectangle_ai\vision_charts_claude_20260506_vision_test\*.png`

Result:

- Mechanical screenshots saved: 46 PNGs.
- Claude-approved trades: 28.
- Wins: 7.
- Losses: 21.
- Open at end: 0.
- Win rate: 25.0%.
- Total R: 0.0.
- Average R: 0.0.
- AI score range: 72 to 82.
- Verification: `sl_not_on_rectangle_edge = 0`.
