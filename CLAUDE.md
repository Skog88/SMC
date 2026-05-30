# CLAUDE.md — SMC Upgrade Implementation Plan
## Project: mt5_rectangle_ai → SMC System

This document is the master implementation plan for upgrading the existing
15m/1m rectangle strategy into a full Smart Money Concepts (SMC) system with
a self-learning feedback loop.

Read this file before touching any code. Follow the phases in order.
Do not skip ahead. Each phase builds on the previous one.

---

## Current System — What Already Works

Do not break these. They are SMC-compatible and stay.

| Component | File | SMC Equivalent |
|---|---|---|
| Weakness sweep (wick + close back) | `strategy/sweep_detector.py` | Liquidity sweep ✅ |
| FVG detector | `strategy/imbalance_detector.py` | Fair Value Gap ✅ |
| Session filter | `core/sessions.py` | Kill zones (needs tightening) |
| M1 flip | `strategy/m1_flip.py` | LTF CHoCH confirmation ✅ |
| Swing High/Low detection | `strategy/structure_detector.py` | Structure detection (needs HTF layer) |
| Rectangle zone | `strategy/rectangle.py` | OB entry zone approximation (needs upgrade) |
| EMA 50/200 filter | `strategy/ema_filter.py` | Direction bias (becomes secondary) |
| State machine | `strategy/state_machine.py` | Keep — add new states |
| Journal + SQLite | `journal/` | Keep — extend schema |
| Risk engine | `execution/risk_engine.py` | Keep — no changes |
| MT5 executor | `execution/mt5_executor.py` | Keep — no changes |

---

## The 3 Core Gaps to Fix

Before writing any code, understand what is actually missing:

**Gap 1 — No HTF Context**
The system is purely M15/M1. It has no awareness of H4 or Daily structure.
SMC requires HTF to define the draw on liquidity — where price is ultimately
going. Without it, M15 setups have no directional anchor beyond EMA slope.

**Gap 2 — Rectangle ≠ Order Block**
The rectangle is drawn from the sweep candle (close to low/high).
An Order Block is the last opposing candle before the impulsive move that
caused the structure break. These overlap but are not the same. The OB is
the institutional origin candle — often several candles before the sweep.

**Gap 3 — Claude Prompt Asks the Wrong Question**
Claude currently receives a chart and returns a single confidence score.
Winners average 75.67, losers average 77.89 — the score is not predictive.
Claude must answer specific, binary SMC criteria — not give an overall score.

---

## Phase 1 — HTF Bias Layer

### Goal
Give the system a higher timeframe anchor so M15 setups are only taken in
the direction of institutional flow.

### What to Build

**New file: `core/htf_engine.py`**

Pull H4 candles for each symbol alongside existing M15/M1 pulls.
From H4 candles, detect the most recent confirmed BOS (Break of Structure):
- Bullish BOS: H4 candle closed above the previous confirmed swing high
- Bearish BOS: H4 candle closed below the previous confirmed swing low

Output a HTF bias object per symbol:
```
{
  "bias": "bullish" | "bearish" | "neutral",
  "last_bos_level": float,
  "last_bos_time": datetime,
  "last_swing_high": float,
  "last_swing_low": float,
  "swing_midpoint": float       # used later for premium/discount
}
```

**Update: `strategy/state_machine.py`**

Add HTF_BIAS_CHECK as the first gate, before M15_CANDIDATE_FOUND.
The EMA filter becomes a secondary confirmation, not the primary direction gate.

**Update: `strategy/skip_reasons.py`**

Add:
```
SKIP_HTF_BIAS_CONFLICT = "SKIP_HTF_BIAS_CONFLICT"
SKIP_HTF_BIAS_NEUTRAL = "SKIP_HTF_BIAS_NEUTRAL"
```

**Update: `core/config_loader.py` and `config.yaml`**

Add HTF config block:
```yaml
htf:
  timeframe: "H4"
  swing_left: 3
  swing_right: 3
  max_bos_age_candles: 50
  require_confirmed_bos: true
```

**Update: journal schema**

Add to `setups` table:
- `htf_bias` TEXT
- `htf_bos_level` REAL
- `htf_last_swing_high` REAL
- `htf_last_swing_low` REAL
- `htf_swing_midpoint` REAL

### State Machine After Phase 1
```
IDLE
  ↓
HTF_BIAS_CHECK          ← NEW
  ↓
M15_CANDIDATE_FOUND
  ↓
M15_WEAKNESS_CONFIRMED
  ... (rest unchanged)
```

### Acceptance Criteria
- [ ] H4 candles pulling correctly for all configured symbols
- [ ] HTF bias correctly identified as bullish/bearish/neutral
- [ ] M15 setups in conflict with H4 bias are rejected with SKIP_HTF_BIAS_CONFLICT
- [ ] HTF fields populated in journal for every setup
- [ ] Backtest re-run shows reduced setup count (counter-trend setups filtered)

---

## Phase 2 — Order Block Classifier

### Goal
Replace the rectangle-only zone with a true SMC Order Block so entry zones
reflect institutional origin candles, not just the sweep candle geometry.

### What to Build

**Update: `strategy/structure_detector.py`**

Add `identify_order_block()` function.

Logic:
1. After a BOS is confirmed on M15 (impulsive move through a swing level),
   look back at the candles that preceded the impulse.
2. Find the last opposing candle before the impulse began:
   - For a bullish setup: the last bearish candle (close < open) before the
     upward impulse that created the swing high
   - For a bearish setup: the last bullish candle (close > open) before the
     downward impulse that created the swing low
3. That candle's body defines the Order Block zone:
   - OB high = max(open, close) of origin candle
   - OB low  = min(open, close) of origin candle

Output an OrderBlock object:
```
{
  "ob_high": float,
  "ob_low": float,
  "ob_origin_time": datetime,
  "ob_timeframe": "M15" | "H4",
  "ob_mitigation_count": int,    # how many times price has entered this zone
  "ob_fvg_overlap": bool,        # FVG exists inside the OB zone
  "ob_valid": bool
}
```

**Update: `strategy/rectangle.py`**

The rectangle remains as the minimum entry zone (sweep candle geometry).
Add validation: does the rectangle overlap with the OB zone?
If yes → `ob_rectangle_overlap: true` (high confluence signal).
If no  → still valid but lower confluence score.

**Update: journal schema**

Add to `setups` table:
- `ob_origin_time` TEXT
- `ob_high` REAL
- `ob_low` REAL
- `ob_timeframe` TEXT
- `ob_mitigation_count` INTEGER
- `ob_fvg_overlap` INTEGER (0/1)
- `ob_rectangle_overlap` INTEGER (0/1)

**Update: `strategy/skip_reasons.py`**

Add:
```
SKIP_NO_ORDER_BLOCK_FOUND = "SKIP_NO_ORDER_BLOCK_FOUND"
SKIP_OB_FULLY_MITIGATED = "SKIP_OB_FULLY_MITIGATED"
```

**Update: `config.yaml`**

```yaml
order_block:
  max_lookback_candles: 20
  require_unmitigated: true
  max_mitigation_count: 1
  min_ob_size_points:
    forex: 5
    metals: 50
    indices: 100
```

### Acceptance Criteria
- [ ] OB correctly identified for bullish and bearish setups on backtests
- [ ] Mitigated OBs are filtered when `require_unmitigated: true`
- [ ] FVG overlap correctly detected and logged
- [ ] OB fields populated in journal for every setup
- [ ] Visual verification: backtest screenshots show OB zone matches chart

---

## Phase 3 — Liquidity Pool Detection

### Goal
Know whether the swept level is a lone swing point or a liquidity pool
(equal highs/lows). Pool sweeps are significantly higher probability.

### What to Build

**New file: `strategy/liquidity_detector.py`**

Scan recent M15 and H4 candles for equal highs and equal lows.
Equal = two or more swing points within a configurable price buffer.

```yaml
liquidity:
  equal_level_buffer_points:
    forex: 5
    metals: 100
    indices: 200
  min_touches: 2
  lookback_candles: 60
```

Classify every swept level:
- `single_swing` — one swing point only
- `double_top` / `double_bottom` — two equal levels
- `triple_top` / `triple_bottom` — three or more equal levels
- `session_high` — Asia/London/NY session extreme
- `session_low` — Asia/London/NY session extreme

Connect to existing `session_levels.py` — if the swept level matches a
session high or low from the prior session, tag it accordingly.

**Update: journal schema**

Add to `setups` table:
- `swept_level_type` TEXT  (single_swing / double_top / triple_top / session_high / etc.)
- `liquidity_pool_touches` INTEGER

### Acceptance Criteria
- [ ] Equal highs/lows correctly identified within configured buffer
- [ ] Session highs/lows correctly matched to swept levels
- [ ] `swept_level_type` populated in journal for all setups
- [ ] Backtest report shows win rate breakdown by swept_level_type

---

## Phase 4 — Kill Zone Filter

### Goal
Restrict trading to institutional activity windows where SMC setups have
the highest probability of following through.

### What to Build

**Update: `core/sessions.py`**

Add `is_kill_zone()` method alongside existing session detection.

Kill zones (Oslo/CET time — adjust for DST):
```yaml
kill_zones:
  london_open:
    start: "08:00"
    end: "10:00"
  new_york_open:
    start: "13:30"
    end: "15:30"
  london_close:
    start: "15:00"
    end: "16:00"
  enabled: true
  hard_filter: true    # if false → log only, do not skip
```

When `hard_filter: true`, setups outside kill zones are logged with
SKIP_OUTSIDE_KILL_ZONE and not sent to AI review.

When `hard_filter: false`, setups outside kill zones proceed but the
journal field `in_kill_zone` is false — useful during data collection
phase to understand the performance difference before enforcing the filter.

**Update: `strategy/skip_reasons.py`**

Add:
```
SKIP_OUTSIDE_KILL_ZONE = "SKIP_OUTSIDE_KILL_ZONE"
```

**Update: journal schema**

Add to `setups` table:
- `in_kill_zone` INTEGER (0/1)
- `kill_zone_name` TEXT (london_open / new_york_open / london_close / none)

### Acceptance Criteria
- [ ] Kill zones correctly computed for all configured symbols
- [ ] DST handling verified for Oslo/CET offset
- [ ] `hard_filter: false` first — collect data before enforcing
- [ ] Backtest report shows win rate inside vs outside kill zones

---

## Phase 5 — Premium / Discount Zone Filter

### Goal
Only take longs in discount (below HTF midpoint), only take shorts in
premium (above HTF midpoint). Eliminates buying at the top and selling
at the bottom of a range.

### What to Build

**Update: `core/htf_engine.py`**

The `swing_midpoint` is already output from Phase 1 (50% of H4 swing range
between last BOS and the previous swing extreme).

Add `get_zone()` method:
```
if current_price < swing_midpoint:
    zone = "discount"
elif current_price > swing_midpoint:
    zone = "premium"
else:
    zone = "equilibrium"
```

Trade rules:
- Long setups valid only in `discount` zone
- Short setups valid only in `premium` zone
- `equilibrium` — start as quality score, not hard filter

**Update: `config.yaml`**

```yaml
premium_discount:
  enabled: true
  hard_filter: false    # start as score, enforce after data confirms edge
  equilibrium_buffer_pct: 5.0
```

**Update: `strategy/skip_reasons.py`**

Add:
```
SKIP_WRONG_PREMIUM_DISCOUNT_ZONE = "SKIP_WRONG_PREMIUM_DISCOUNT_ZONE"
```

**Update: journal schema**

Add to `setups` table:
- `zone_type` TEXT (premium / discount / equilibrium)
- `distance_from_midpoint_pct` REAL

### Acceptance Criteria
- [ ] Zone correctly classified for all setups
- [ ] `hard_filter: false` initially — run as score first
- [ ] Journal shows zone_type populated for all setups
- [ ] Backtest shows win rate breakdown: discount longs vs premium longs

---

## Phase 6 — Claude Prompt Redesign

### Goal
Replace the single confidence score with a structured SMC checklist that
produces verifiable, auditable, per-criterion answers.

### The Problem with the Current Prompt

Current prompt asks: "Is this a quality setup? Confidence 0–100."
Winners average 75.67. Losers average 77.89. This is noise, not signal.

### New Prompt Architecture

**Update: `ai/prompt_builder.py`**

The prompt now sends structured market context as JSON plus the chart image,
and asks Claude to answer a specific checklist — not give an overall score.

Claude is given the following context object alongside the chart image:
```
{
  "symbol": "GBPUSD",
  "direction": "short",
  "htf_bias": "bearish",
  "session": "london_open",
  "in_kill_zone": true,
  "swept_level_type": "double_top",
  "zone_type": "premium",
  "ob_fvg_overlap": true,
  "ob_mitigation_count": 0,
  "ob_rectangle_overlap": true
}
```

Claude is asked to answer only these questions — each binary yes/no:

1. Is the sweep candle clean? (clear wick with close back inside the level)
2. Is the sweep level a clean liquidity pool? (equal highs/lows visible)
3. Is there visible imbalance (FVG) inside or near the entry zone?
4. Is the Order Block origin clearly visible as an impulsive move?
5. Is the HTF bias confirmed by the visible chart structure?
6. Is there a visible draw on liquidity above (for shorts) or below (for longs)?
7. Would an SMC trader take this setup as shown, with no hesitation?

Claude returns:
```json
{
  "answers": {
    "clean_sweep": true,
    "liquidity_pool": true,
    "fvg_present": true,
    "ob_visible": true,
    "htf_confirmed": true,
    "draw_visible": false,
    "would_trade": true
  },
  "confluence_count": 6,
  "rejection_reason": null
}
```

No overall confidence score. The `confluence_count` IS the score.
`would_trade: false` is an automatic rejection regardless of confluence_count.

**Update: `ai/prompt_builder.py`**

Add prompt versioning to the filename: `prompt_v3_smc_checklist.txt`
Always log which prompt version produced each AI review.

**Update: `ai/response_parser.py`**

Parse the new structured response. Store each individual answer.

**Update: `config.yaml`**

```yaml
ai:
  enabled: true
  prompt_version: "v3_smc_checklist"
  min_confluence_count: 5        # out of 7 criteria
  require_would_trade: true
  reject_on_invalid_json: true
  timeout_seconds: 30
```

**Update: journal schema**

Replace single confidence_score field in `ai_reviews` with:
- `confluence_count` INTEGER
- `clean_sweep` INTEGER (0/1)
- `liquidity_pool` INTEGER (0/1)
- `fvg_present` INTEGER (0/1)
- `ob_visible` INTEGER (0/1)
- `htf_confirmed` INTEGER (0/1)
- `draw_visible` INTEGER (0/1)
- `would_trade` INTEGER (0/1)
- `rejection_reason` TEXT
- `prompt_version` TEXT

### Acceptance Criteria
- [ ] New prompt produces valid JSON for 95%+ of setups
- [ ] Each criterion stored individually in ai_reviews
- [ ] Prompt version logged for every review
- [ ] Backtest comparison: v2 (old) vs v3 (new) on same setup dataset
- [ ] Per-criterion accuracy report is possible from journal queries

---

## Phase 7 — Confluence Scoring Engine

### Goal
Replace the binary approve/reject gate with a weighted confluence score
that combines mechanical signals and Claude's checklist answers.

### What to Build

**New file: `strategy/confluence_scorer.py`**

The scorer receives the full setup context and Claude's checklist answers
and produces a single weighted confluence score.

Score weights (configurable in config.yaml):

```yaml
confluence_weights:
  htf_bias_aligned: 20
  in_kill_zone: 20
  swept_liquidity_pool: 15        # double_top / triple_top / session level
  ob_unmitigated: 15
  ob_fvg_overlap: 10
  premium_discount_correct: 10
  claude_clean_sweep: 5
  claude_ob_visible: 5
  claude_draw_visible: 5
  claude_would_trade: -999        # auto-reject if false

  # Bonus criteria (positive)
  ob_rectangle_overlap: 5
  ob_h4_timeframe: 10             # H4 OB is stronger than M15 OB

  # Penalty criteria (negative)
  ob_mitigation_count_1: -10
  ob_mitigation_count_2plus: -25
  outside_kill_zone: -30
```

Minimum score to trade: configurable per symbol.
Score is logged in journal. Reports later show score vs R-multiple distribution.

**Update: `strategy/state_machine.py`**

The AI_APPROVED state is now CONFLUENCE_SCORE_CALCULATED.
The gate condition is `confluence_score >= min_score` not `confidence >= threshold`.

**Update: journal schema**

Add to `setups` table:
- `confluence_score` REAL
- `confluence_score_breakdown` TEXT (JSON of each component)
- `min_score_required` REAL

**Update: `strategy/skip_reasons.py`**

Add:
```
SKIP_CONFLUENCE_SCORE_TOO_LOW = "SKIP_CONFLUENCE_SCORE_TOO_LOW"
```

### Acceptance Criteria
- [ ] Confluence score correctly computed for all setups
- [ ] Score breakdown stored as JSON in journal
- [ ] Backtest shows score distribution for winners vs losers
- [ ] Minimum score threshold findable from backtest data (not guessed)

---

## Phase 8 — Journal Schema Upgrade + Counterfactual Tracker

### Goal
Ensure the journal captures everything needed for the self-learning loops.
The counterfactual tracker is the most important addition — it measures
the cost of every rejection.

### What to Build

**New file: `journal/counterfactual_tracker.py`**

For every setup that is skipped, rejected by AI, or filtered by any rule:
- Record the planned entry, SL, and TP at the time of rejection
- Monitor subsequent M1 candles in the background
- Log whether price would have hit TP, SL, or neither within a time window
- Store result in `counterfactuals` table

This answers the critical question: "When Claude rejects a setup, is it
actually a good rejection or are we leaving money on the table?"

**New table: `counterfactuals`**
```sql
CREATE TABLE counterfactuals (
    id TEXT PRIMARY KEY,
    setup_id TEXT,
    skip_reason TEXT,
    planned_entry REAL,
    planned_sl REAL,
    planned_tp REAL,
    planned_rr REAL,
    hypothetical_outcome TEXT,    -- TP_HIT / SL_HIT / EXPIRED / OPEN
    hypothetical_pnl_r REAL,
    monitoring_end_time TEXT,
    created_at TEXT,
    FOREIGN KEY(setup_id) REFERENCES setups(setup_id)
);
```

**New table: `confluence_breakdown`**
```sql
CREATE TABLE confluence_breakdown (
    id TEXT PRIMARY KEY,
    setup_id TEXT,
    criterion TEXT,
    value REAL,
    weight REAL,
    contribution REAL,
    created_at TEXT,
    FOREIGN KEY(setup_id) REFERENCES setups(setup_id)
);
```

**Update: `journal/reports.py`**

Add the following reports (these power the self-learning loops):

Report 1 — Criterion Win Rate
For each Claude criterion (clean_sweep, fvg_present, etc.):
what is the win rate of setups where Claude answered yes vs no?

Report 2 — Score Distribution
Histogram of confluence_score for winners vs losers.
Identifies the true minimum score threshold.

Report 3 — Counterfactual Cost
For each skip reason: what % of rejections were actually profitable?
This directly shows which filter is over-filtering.

Report 4 — Kill Zone Performance
Win rate, avg R, and setup count inside vs outside each kill zone.

Report 5 — Swept Level Type Performance
Win rate and avg R by swept_level_type (single_swing vs double_top vs session_high, etc.)

Report 6 — Prompt Version Comparison
Side-by-side accuracy of each Claude criterion per prompt version.

### Acceptance Criteria
- [ ] Counterfactual tracker runs silently in background for all skipped setups
- [ ] All 6 reports produce valid output from journal data
- [ ] No setup passes through the system without full journal coverage
- [ ] Schema migration script handles existing data cleanly

---

## Updated State Machine (All Phases Complete)

```
IDLE
  ↓
HTF_BIAS_CHECK                    ← Phase 1
  ↓
M15_CANDIDATE_FOUND
  ↓
LIQUIDITY_POOL_CLASSIFIED         ← Phase 3
  ↓
ORDER_BLOCK_IDENTIFIED            ← Phase 2
  ↓
KILL_ZONE_CHECKED                 ← Phase 4
  ↓
PREMIUM_DISCOUNT_CHECKED          ← Phase 5
  ↓
M15_WEAKNESS_CONFIRMED
  ↓
AI_REVIEW_PENDING
  ↓
CONFLUENCE_SCORE_CALCULATED       ← Phase 7
  ↓
RECTANGLE_ACTIVE
  ↓
M1_FLIP_CONFIRMED
  ↓
ORDER_SENT
  ↓
POSITION_OPEN
  ↓
POSITION_CLOSED
  ↓
JOURNAL_COMPLETE                  ← Phase 8 counterfactual also logged here
```

New skip reasons added across all phases:
```
SKIP_HTF_BIAS_CONFLICT
SKIP_HTF_BIAS_NEUTRAL
SKIP_NO_ORDER_BLOCK_FOUND
SKIP_OB_FULLY_MITIGATED
SKIP_OUTSIDE_KILL_ZONE
SKIP_WRONG_PREMIUM_DISCOUNT_ZONE
SKIP_CONFLUENCE_SCORE_TOO_LOW
```

---

## Updated Folder Structure

```
mt5_rectangle_ai/
│
├── CLAUDE.md                          ← this file
├── main.py
├── config.yaml
├── requirements.txt
│
├── core/
│   ├── data_engine.py
│   ├── candle_builder.py
│   ├── symbol_config.py
│   ├── config_loader.py
│   ├── sessions.py                    ← add is_kill_zone()
│   └── htf_engine.py                  ← NEW Phase 1
│
├── strategy/
│   ├── ema_filter.py                  ← demoted to secondary filter
│   ├── structure_detector.py          ← add identify_order_block()
│   ├── imbalance_detector.py
│   ├── session_levels.py
│   ├── sweep_detector.py
│   ├── liquidity_detector.py          ← NEW Phase 3
│   ├── confluence_scorer.py           ← NEW Phase 7
│   ├── rectangle.py
│   ├── m1_flip.py
│   ├── signal_builder.py
│   ├── skip_reasons.py                ← add new reasons each phase
│   └── state_machine.py              ← updated each phase
│
├── ai/
│   ├── claude_client.py
│   ├── vision_client.py
│   ├── prompt_builder.py              ← Phase 6 redesign
│   ├── response_parser.py             ← Phase 6 redesign
│   └── prompt_versions/
│       ├── prompt_v2_quality.txt      ← current (broken)
│       └── prompt_v3_smc_checklist.txt ← Phase 6 target
│
├── execution/
│   ├── risk_engine.py
│   ├── position_sizer.py
│   ├── mt5_executor.py
│   └── trade_monitor.py
│
├── journal/
│   ├── db.py
│   ├── schema.sql                     ← extended each phase
│   ├── setup_logger.py
│   ├── ai_logger.py
│   ├── trade_logger.py
│   ├── counterfactual_tracker.py      ← NEW Phase 8
│   ├── screenshot_logger.py
│   └── reports.py                    ← 6 new reports Phase 8
│
├── backtesting/
│   ├── mechanical_backtest.py
│   ├── fetch_historical.py
│   └── generate_tv_indicator.py
│
├── dashboards/
│   └── local_dashboard.py
│
└── data/
    ├── journal.sqlite
    ├── historical/
    ├── screenshots/
    └── reports/
```

---

## Self-Learning Loops (Post Phase 8)

Once all 8 phases are complete and paper trading has produced 50+ outcomes,
activate the feedback loops in this order:

### Loop 1 — LLM Loop (Prompt Evolution)
Every 4 weeks, run Report 6 (Prompt Version Comparison).
Identify which criteria Claude answers incorrectly most often.
Update prompt_v4 to correct those specific failure modes.
Never change the prompt mid-run. Version and date every change.

### Loop 2 — RAG Loop (Historical Context in Prompt)
When journal has 50+ completed outcomes:
Before sending a setup to Claude, query the journal for the 3 most similar
historical setups by: same symbol, same session, same swept_level_type,
similar confluence_score. Include those examples in the prompt with outcomes.
Claude now reasons with historical precedent, not just the current chart.

### Loop 3 — ML Loop (Feature → Config Updates)
When journal has 100+ completed outcomes:
Run Report 2 (Score Distribution) and Report 5 (Swept Level Type Performance).
Identify which confluence weights are over or under-valued.
Adjust confluence_weights in config.yaml based on data.
Re-run backtest on historical data to validate before applying live.

### Loop 4 — RL Loop (Parameter Sensitivity)
When journal has 200+ completed outcomes:
Run a parameter sensitivity report: vary each config threshold ±10–20%
and calculate effect on expected R.
Adjust thresholds in the direction of higher expected R.
One parameter at a time. Document every change and the data that justified it.

---

## Rules for Claude Code

1. **Never modify the risk engine or MT5 executor without explicit instruction.**
   These touch real money.

2. **Always add new skip reasons to `skip_reasons.py` before using them.**
   Never use raw strings for skip reasons in logic files.

3. **Every new filter starts as `hard_filter: false`.**
   Collect data first. Enforce later when evidence exists.

4. **Every journal schema change needs a migration.**
   Never ALTER TABLE without a migration script that handles existing rows.

5. **Every phase ends with a backtest re-run.**
   The acceptance criteria must be verified before moving to the next phase.

6. **Prompt versions are never edited — only versioned.**
   `prompt_v2` stays frozen. Changes go into `prompt_v3`, `prompt_v4`, etc.

7. **The counterfactual tracker must never block execution.**
   Run it asynchronously. A failure in counterfactual tracking must not
   prevent a trade from being placed.

8. **Config.yaml is the single source of truth for all thresholds.**
   No magic numbers in code. Every threshold in config.

---

## Current System Status (as of last session)

Working:
- Project scaffold and all Phase 1 (original) modules
- MT5 MCP integration
- Mechanical backtest runner
- Per-symbol config loader
- SQLite journal V0.1
- Claude vision gate (broken prompt — Phase 6 target)
- TradingView Pine Script indicator
- Historical data fetch and local cache

Not yet built:
- Daemon loop (live/paper trading scheduler)
- HTF data layer (Phase 1 of this plan)
- Order Block classifier (Phase 2)
- Liquidity pool detector (Phase 3)
- Kill zone hard filter (Phase 4)
- Premium/discount filter (Phase 5)
- SMC Claude prompt v3 (Phase 6)
- Confluence scoring engine (Phase 7)
- Counterfactual tracker (Phase 8)
- 6 self-learning reports (Phase 8)

Start at Phase 1. Do not skip. commit and push tp git after each step.
