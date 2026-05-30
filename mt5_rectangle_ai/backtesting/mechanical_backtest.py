"""Mechanical Phase 1 backtest runner.

This runner intentionally skips Claude and live execution. It uses the current
rule engine, auto-approves mechanically valid setups, waits for the configured
M1 flip, then simulates fixed SL/TP outcomes from subsequent M1 candles.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Iterable

from core.candle_builder import Candle

from core.config_loader import load_rule_engine_config
from core.local_data_engine import LocalDataEngine
from strategy import skip_reasons as decisions
from strategy.state_machine import RuleDecision, SymbolRuleState


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    setup_id: str
    symbol: str
    direction: str
    setup_time: str
    entry_time: str
    entry_price: float
    sl: float
    tp: float
    planned_rr: float
    exit_time: str | None
    exit_price: float | None
    exit_reason: str
    pnl_r: float
    rectangle_size_points: float
    rectangle_low: float
    rectangle_high: float
    ai_score: int


@dataclass(frozen=True, slots=True)
class BacktestSummary:
    symbol: str
    start: str
    end: str
    m15_bars: int
    m1_bars: int
    setups: int
    trades: int
    wins: int
    losses: int
    breakevens: int
    open_at_end: int
    win_rate: float
    total_r: float
    average_r: float


def run_symbol_backtest(
    symbol: str,
    days: int = 14,
    sl_buffer_points: float | None = None,
    end_time: datetime | None = None,
    use_vision: bool = False,
    ma_period: int = 60,
    breakeven_r: float = 2.0,
    data_dir: Path | None = None,
    disable_htf: bool = False,
) -> tuple[BacktestSummary, list[BacktestTrade]]:
    if data_dir is not None:
        engine = LocalDataEngine(data_dir)
    else:
        from core.data_engine import Mt5DataEngine  # only needed for live MT5 mode
        engine = Mt5DataEngine()
    info = engine.symbol_info(symbol)
    from execution.position_sizer import SymbolMeta
    point = float(info.get("point", 0.00001))
    meta = SymbolMeta(
        symbol=str(info.get("name", symbol)),
        trade_tick_size=point,
        trade_tick_value=point,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        digits=int(info.get("digits", 5)),
        point=point,
    )
    rule_config = load_rule_engine_config(symbol)
    if sl_buffer_points is not None:
        rule_config = replace(rule_config, sl_buffer_points=sl_buffer_points)
    end_time = end_time or datetime.utcnow()
    start_time = end_time - timedelta(days=days)

    # Request enough bars for 24/5 markets plus margin. The returned broker
    # history may contain fewer bars if the market was closed.
    m15 = [
        c
        for c in engine.get_candles(symbol, "M15", days * 24 * 4 + 300, drop_current=False)
        if start_time <= c.time <= end_time
    ]
    m1 = [
        c
        for c in engine.get_candles(symbol, "M1", days * 24 * 60 + 1200, drop_current=False)
        if start_time <= c.time <= end_time
    ]

    # H4 candles: fetch with generous warmup for HTF swing detection
    try:
        all_h4: list[Candle] = engine.get_candles(
            symbol, "H4", days * 6 + 300, drop_current=False
        )
    except FileNotFoundError:
        all_h4 = []

    trades: list[BacktestTrade] = []
    seen_setups: set[str] = set()

    # Keep warmup bars before the test window when available.
    warm_m15 = engine.get_candles(symbol, "M15", days * 24 * 4 + 700, drop_current=False)
    for index, candle in enumerate(warm_m15):
        if candle.time < start_time:
            continue
        if candle.time > end_time:
            break
        history = warm_m15[: index + 1]

        # H4 candles confirmed before the current M15 bar (4h close offset prevents look-ahead)
        if disable_htf or not all_h4:
            h4_history = None
        else:
            h4_cutoff = candle.time - timedelta(hours=4)
            h4_history = [c for c in all_h4 if c.time <= h4_cutoff]

        state = SymbolRuleState(symbol, meta.point, rule_config)
        try:
            decision = state.scan_m15(history, h4_candles=h4_history, use_vision=use_vision)
        except ValueError:
            continue
        if decision.decision != decisions.RECTANGLE_ACTIVE_WAITING_FOR_M1 or decision.setup is None:
            continue
        setup_id = decision.setup["setup_id"]
        if setup_id in seen_setups:
            continue
        seen_setups.add(setup_id)

        # ── MA filter ─────────────────────────────────────────────────────────
        if ma_period > 0:
            if len(history) < ma_period:
                continue  # not enough warmup bars to compute MA reliably
            ma_value = mean(c.close for c in history[-ma_period:])
            setup_direction = "buy" if setup_id.endswith("_LONG") else "sell"
            if setup_direction == "buy" and candle.close < ma_value:
                continue
            if setup_direction == "sell" and candle.close > ma_value:
                continue

        m1_after_rectangle = [bar for bar in m1 if bar.time >= candle.time + timedelta(minutes=15)]
        entry_decision = state.check_m1_flip(m1_after_rectangle)
        if entry_decision.decision != decisions.ENTRY_SIGNAL_READY or entry_decision.entry_signal is None:
            continue

        trade = simulate_trade(decision, entry_decision, m1, breakeven_r=breakeven_r)
        trades.append(trade)

    summary = summarize(symbol, start_time, end_time, len(m15), len(m1), len(seen_setups), trades)
    return summary, trades


def simulate_trade(
    setup_decision: RuleDecision,
    entry_decision: RuleDecision,
    m1: list,
    breakeven_r: float = 2.0,
) -> BacktestTrade:
    setup = setup_decision.setup or {}
    signal = entry_decision.entry_signal or {}
    direction = signal["direction"]
    entry_time = datetime.fromisoformat(signal["m1_trigger_time"])
    later = [bar for bar in m1 if bar.time > entry_time]
    sl = float(signal["sl"])
    tp = float(signal["tp"])
    entry = float(signal["entry_price"])
    rectangle_low = float(signal["rectangle_low"])
    rectangle_high = float(signal["rectangle_high"])
    exit_time: str | None = None
    exit_price: float | None = None
    exit_reason = "OPEN_AT_END"
    pnl_r = 0.0

    # Breakeven state
    use_be = breakeven_r > 0
    risk = abs(entry - sl)
    be_trigger = (entry + breakeven_r * risk) if direction == "buy" else (entry - breakeven_r * risk)
    current_sl = sl
    be_active = False  # becomes True once price reaches breakeven_r * R

    for bar in later:
        if direction == "buy":
            # Check BE trigger only when BE is enabled and not yet triggered
            if use_be and not be_active:
                if bar.low <= current_sl and bar.high >= be_trigger:
                    # Ambiguous: hit original SL and BE trigger same bar → SL first (conservative)
                    exit_time, exit_price, exit_reason, pnl_r = bar.time.isoformat(), current_sl, "AMBIGUOUS_SL_FIRST", -1.0
                    break
                if bar.high >= be_trigger:
                    be_active = True
                    current_sl = entry
                elif bar.low <= current_sl:
                    exit_time, exit_price, exit_reason, pnl_r = bar.time.isoformat(), current_sl, "SL_HIT", -1.0
                    break

            hit_sl = bar.low <= current_sl
            hit_tp = bar.high >= tp
            be_hit = use_be and be_active

            if hit_sl and hit_tp:
                reason = "BREAKEVEN" if be_hit else "AMBIGUOUS_SL_FIRST"
                price_out = entry if be_hit else current_sl
                pnl_out = 0.0 if be_hit else -1.0
                exit_time, exit_price, exit_reason, pnl_r = bar.time.isoformat(), price_out, reason, pnl_out
                break
            if hit_sl:
                reason = "BREAKEVEN" if be_hit else "SL_HIT"
                price_out = entry if be_hit else current_sl
                pnl_out = 0.0 if be_hit else -1.0
                exit_time, exit_price, exit_reason, pnl_r = bar.time.isoformat(), price_out, reason, pnl_out
                break
            if hit_tp:
                exit_time, exit_price, exit_reason, pnl_r = bar.time.isoformat(), tp, "TP_HIT", float(signal["planned_rr"])
                break

        else:  # sell
            if use_be and not be_active:
                if bar.high >= current_sl and bar.low <= be_trigger:
                    exit_time, exit_price, exit_reason, pnl_r = bar.time.isoformat(), current_sl, "AMBIGUOUS_SL_FIRST", -1.0
                    break
                if bar.low <= be_trigger:
                    be_active = True
                    current_sl = entry
                elif bar.high >= current_sl:
                    exit_time, exit_price, exit_reason, pnl_r = bar.time.isoformat(), current_sl, "SL_HIT", -1.0
                    break

            hit_sl = bar.high >= current_sl
            hit_tp = bar.low <= tp
            be_hit = use_be and be_active

            if hit_sl and hit_tp:
                reason = "BREAKEVEN" if be_hit else "AMBIGUOUS_SL_FIRST"
                price_out = entry if be_hit else current_sl
                pnl_out = 0.0 if be_hit else -1.0
                exit_time, exit_price, exit_reason, pnl_r = bar.time.isoformat(), price_out, reason, pnl_out
                break
            if hit_sl:
                reason = "BREAKEVEN" if be_hit else "SL_HIT"
                price_out = entry if be_hit else current_sl
                pnl_out = 0.0 if be_hit else -1.0
                exit_time, exit_price, exit_reason, pnl_r = bar.time.isoformat(), price_out, reason, pnl_out
                break
            if hit_tp:
                exit_time, exit_price, exit_reason, pnl_r = bar.time.isoformat(), tp, "TP_HIT", float(signal["planned_rr"])
                break

    return BacktestTrade(
        setup_id=setup["setup_id"],
        symbol=setup["symbol"],
        direction=direction,
        setup_time=setup["sweep"]["trigger_time"],
        entry_time=signal["m1_trigger_time"],
        entry_price=entry,
        sl=sl,
        tp=tp,
        planned_rr=float(signal["planned_rr"]),
        exit_time=exit_time,
        exit_price=exit_price,
        exit_reason=exit_reason,
        pnl_r=pnl_r,
        rectangle_size_points=float(setup["rectangle"]["size_points"]),
        rectangle_low=rectangle_low,
        rectangle_high=rectangle_high,
        ai_score=int(setup.get("vision_review", {}).get("confidence", 100)),
    )


def summarize(
    symbol: str,
    start_time: datetime,
    end_time: datetime,
    m15_bars: int,
    m1_bars: int,
    setup_count: int,
    trades: list[BacktestTrade],
) -> BacktestSummary:
    wins = sum(1 for trade in trades if trade.pnl_r > 0)
    losses = sum(1 for trade in trades if trade.pnl_r < 0)
    breakevens = sum(1 for trade in trades if trade.pnl_r == 0 and trade.exit_reason != "OPEN_AT_END")
    open_at_end = sum(1 for trade in trades if trade.exit_reason == "OPEN_AT_END")
    closed = wins + losses + breakevens
    pnl_values = [trade.pnl_r for trade in trades]
    return BacktestSummary(
        symbol=symbol,
        start=start_time.isoformat(timespec="seconds"),
        end=end_time.isoformat(timespec="seconds"),
        m15_bars=m15_bars,
        m1_bars=m1_bars,
        setups=setup_count,
        trades=len(trades),
        wins=wins,
        losses=losses,
        breakevens=breakevens,
        open_at_end=open_at_end,
        win_rate=(wins / closed * 100) if closed else 0.0,
        total_r=sum(pnl_values),
        average_r=mean(pnl_values) if pnl_values else 0.0,
    )


def write_outputs(symbol: str, summary: BacktestSummary, trades: list[BacktestTrade]) -> tuple[Path, Path]:
    output_dir = PROJECT_ROOT / "data" / "reports" / "backtests"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = output_dir / f"{symbol}_{stamp}_summary.json"
    trades_path = output_dir / f"{symbol}_{stamp}_trades.csv"
    summary_path.write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")
    with trades_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(BacktestTrade.__dataclass_fields__.keys()))
        writer.writeheader()
        for trade in trades:
            writer.writerow(asdict(trade))
    return summary_path, trades_path


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run mechanical rectangle-strategy backtest.")
    parser.add_argument("--symbol", default="NAS100")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--sl-buffer-points", type=float, default=None)
    parser.add_argument("--end-time", default=None, help="Fixed inclusive end time, e.g. 2026-05-05T13:12:50")
    parser.add_argument("--use-vision", action="store_true", help="Send mechanical M15 setups to Claude vision.")
    parser.add_argument("--ma-period", type=int, default=60, help="MA period for trend filter (0 = disabled).")
    parser.add_argument("--breakeven-r", type=float, default=2.0, help="Move SL to entry when trade reaches this multiple of R (0 = disabled).")
    parser.add_argument("--data-dir", default=None, help="Load candles from cached CSVs instead of MT5 (path to historical data folder).")
    parser.add_argument("--no-htf", action="store_true", help="Disable HTF bias filter (Phase 1) for baseline comparison.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    fixed_end = datetime.fromisoformat(args.end_time) if args.end_time else None
    data_dir = Path(args.data_dir) if args.data_dir else None
    summary, trades = run_symbol_backtest(
        args.symbol.upper(),
        args.days,
        args.sl_buffer_points,
        fixed_end,
        args.use_vision,
        args.ma_period,
        args.breakeven_r,
        data_dir,
        disable_htf=args.no_htf,
    )
    summary_path, trades_path = write_outputs(args.symbol.upper(), summary, trades)
    print(json.dumps(asdict(summary), indent=2))
    print(f"summary_path={summary_path}")
    print(f"trades_path={trades_path}")


if __name__ == "__main__":
    main()
