"""Generate a TradingView Pine Script indicator from backtest trade CSVs.

Finds the latest backtest CSV for each symbol, converts timestamps to Unix ms,
and writes a Pine Script file that draws entry/exit labels, SL/TP lines, and
a shaded rectangle box showing the sweep zone.

When a Claude vision confidence-breakdown CSV exists, GBPUSD is generated from
that latest vision test instead of the all-mechanical backtest. The vision CSV
does not contain prices, so price geometry is taken from the latest mechanical
GBPUSD trade CSV and converted to the no-buffer SL/TP policy used by that test.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = PROJECT_ROOT / "data" / "reports" / "backtests"
OUTPUT_DIR   = PROJECT_ROOT / "data" / "reports"
VISION_BREAKDOWN = PROJECT_ROOT / "vision_confidence_breakdown_GBPUSD_v2.csv"
SYMBOLS      = ["EURUSD", "GBPUSD", "NAS100", "XAUUSD"]


def to_unix_ms(ts_str: str) -> int:
    dt = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def latest_trades(symbol: str) -> list[dict]:
    files = sorted(BACKTEST_DIR.glob(f"{symbol}_*_trades.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files:
        with path.open(encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if "rectangle_low" not in (reader.fieldnames or []) or "rectangle_high" not in (reader.fieldnames or []):
                continue
            return [row for row in reader if row.get("entry_time") and row.get("exit_time")]
    return []


def latest_vision_gbpusd_trades() -> list[dict]:
    """Return Claude v2 GBPUSD no-buffer trades for TradingView drawing."""
    if not VISION_BREAKDOWN.exists():
        return []

    mechanical_by_setup = {row["setup_time"]: row for row in latest_trades("GBPUSD")}
    trades: list[dict] = []
    with VISION_BREAKDOWN.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if not row.get("entry_time") or not row.get("exit_time"):
                continue

            base = mechanical_by_setup.get(row["setup_time"])
            if base is None:
                continue

            trade = dict(base)
            trade["direction"] = row["direction"]
            trade["entry_time"] = row["entry_time"]
            trade["exit_time"] = row["exit_time"]
            trade["exit_reason"] = row["exit_reason"]
            trade["pnl_r"] = row["pnl_r"]
            trade["ai_score"] = row["confidence"]

            rect_low = float(base["rectangle_low"])
            rect_high = float(base["rectangle_high"])
            entry = float(trade["entry_price"])
            planned_rr = float(trade.get("planned_rr") or 3.0)
            if trade["direction"] == "buy":
                sl = rect_low
                tp = entry + (entry - sl) * planned_rr
            else:
                sl = rect_high
                tp = entry - (sl - entry) * planned_rr

            trade["sl"] = round(sl, 8)
            trade["tp"] = round(tp, 8)
            trade["exit_price"] = trade["tp"] if float(trade["pnl_r"]) > 0 else trade["sl"]
            trades.append(trade)

    return trades


def pine_array(name: str, values: list) -> str:
    items = ", ".join(str(v) for v in values)
    return f"var {name} = array.from({items})"


def build_pine_script(all_trades: dict[str, list[dict]]) -> str:
    blocks: list[str] = []

    sym_var_map: dict[str, str] = {}
    for sym, trades in all_trades.items():
        if not trades:
            continue
        prefix = sym.lower().replace(".", "_")
        sym_var_map[sym] = prefix

        setup_ts  = [to_unix_ms(t["setup_time"])  for t in trades]
        entry_ts  = [to_unix_ms(t["entry_time"])  for t in trades]
        exit_ts   = [to_unix_ms(t["exit_time"])   for t in trades]
        entry_px  = [float(t["entry_price"])       for t in trades]
        sl_px     = [float(t["sl"])                for t in trades]
        tp_px     = [float(t["tp"])                for t in trades]
        dirs      = [1 if t["direction"] == "buy" else -1 for t in trades]
        pnls      = [float(t["pnl_r"])             for t in trades]
        rect_lo   = [float(t["rectangle_low"])     for t in trades]
        rect_hi   = [float(t["rectangle_high"])    for t in trades]

        blocks.append(f"// ---- {sym} ----")
        blocks.append(pine_array(f"{prefix}_sts",  setup_ts))
        blocks.append(pine_array(f"{prefix}_ets",  entry_ts))
        blocks.append(pine_array(f"{prefix}_xts",  exit_ts))
        blocks.append(pine_array(f"{prefix}_epx",  entry_px))
        blocks.append(pine_array(f"{prefix}_sl",   sl_px))
        blocks.append(pine_array(f"{prefix}_tp",   tp_px))
        blocks.append(pine_array(f"{prefix}_dir",  dirs))
        blocks.append(pine_array(f"{prefix}_pnl",  pnls))
        blocks.append(pine_array(f"{prefix}_rlo",  rect_lo))
        blocks.append(pine_array(f"{prefix}_rhi",  rect_hi))
        blocks.append("")

    draw_fn = """\
draw_trades(sts, ets, xts, epx, sl_arr, tp_arr, dir_arr, pnl_arr, rlo, rhi) =>
    n = array.size(ets)
    for i = 0 to n - 1
        st   = array.get(sts,   i)
        et   = array.get(ets,   i)
        xt   = array.get(xts,   i)
        ep   = array.get(epx,   i)
        sl   = array.get(sl_arr, i)
        tp   = array.get(tp_arr, i)
        d    = array.get(dir_arr, i)
        pnl  = array.get(pnl_arr, i)
        rl   = array.get(rlo,   i)
        rh   = array.get(rhi,   i)
        win  = pnl > 0

        entry_col = d == 1 ? color.new(#2196F3, 0) : color.new(#FF5722, 0)
        exit_col  = win  ? color.new(#4CAF50, 0)  : color.new(#F44336, 0)

        // Rectangle zone box spans full trade so it is easy to see
        // Left edge = setup candle (sweep wick), right edge = exit
        box.new(st, rh, xt, rl,
                xloc        = xloc.bar_time,
                bgcolor     = color.new(entry_col, 85),
                border_color = entry_col,
                border_width = 1)

        // Entry arrow pinned at entry price
        label.new(et, ep,
                  text      = d == 1 ? "BUY ENTRY" : "SELL ENTRY",
                  xloc      = xloc.bar_time,
                  style     = d == 1 ? label.style_label_upper_left
                                     : label.style_label_lower_left,
                  color     = entry_col,
                  textcolor = color.white,
                  size      = size.small)

        // Exit label at TP or SL price level
        label.new(xt, win ? tp : sl,
                  text      = win ? "WIN +" + str.tostring(pnl, "#.#") + "R"
                                  : "LOSS " + str.tostring(pnl, "#.#") + "R",
                  xloc      = xloc.bar_time,
                  style     = label.style_label_left,
                  color     = exit_col,
                  textcolor = color.white,
                  size      = size.small)

        // Entry price line
        line.new(et, ep, xt, ep,
                 xloc  = xloc.bar_time,
                 color = entry_col,
                 width = 1)

        // SL line
        line.new(et, sl, xt, sl,
                 xloc  = xloc.bar_time,
                 color = color.new(#F44336, 50),
                 style = line.style_dashed)

        // TP line
        line.new(et, tp, xt, tp,
                 xloc  = xloc.bar_time,
                 color = color.new(#4CAF50, 50),
                 style = line.style_dashed)
"""

    dispatch_lines: list[str] = []
    for sym, prefix in sym_var_map.items():
        dispatch_lines.append(
            f'if barstate.islast and str.contains(syminfo.tickerid, "{sym}")'
        )
        dispatch_lines.append(
            f"    draw_trades({prefix}_sts, {prefix}_ets, {prefix}_xts, {prefix}_epx,"
            f" {prefix}_sl, {prefix}_tp, {prefix}_dir, {prefix}_pnl,"
            f" {prefix}_rlo, {prefix}_rhi)"
        )

    header = """\
//@version=6
// Rectangle AI Backtest Markers - auto-generated, do not edit by hand
// CSV timestamps are UTC; TradingView displays them in the chart timezone.
indicator("Rectangle AI Backtest", overlay=true,
          max_labels_count=500, max_lines_count=500, max_boxes_count=500)
"""

    total = sum(len(t) for t in all_trades.values())
    lines = [
        header,
        *blocks,
        draw_fn,
        *dispatch_lines,
        "",
        f"// {total} total trades across {len(sym_var_map)} symbol(s)",
    ]
    return "\n".join(lines)


def main() -> None:
    all_trades = {sym: latest_trades(sym) for sym in SYMBOLS}

    for sym, trades in all_trades.items():
        print(f"{sym}: {len(trades)} trade(s)")
    script = build_pine_script(all_trades)
    out_path = OUTPUT_DIR / "tv_backtest_markers.pine"
    out_path.write_text(script, encoding="utf-8")
    print(f"\nWrote: {out_path}")
    print(f"Lines: {script.count(chr(10))}")


if __name__ == "__main__":
    main()
