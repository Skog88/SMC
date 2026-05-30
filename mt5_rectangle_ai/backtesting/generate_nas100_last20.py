"""Generate TradingView Pine Script for the last 40 trades from the filtered NAS100 backtest.

Reads from patbd_nas100_filtered_trades.csv (Asia+London + mom6, TP=3R, BE@2R).
"""

import csv
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "data" / "reports" / "backtests" / "patbd_nas100_filtered_trades.csv"
OUT_PATH = PROJECT_ROOT / "data" / "reports" / "nas100_last20_trades.pine"


def to_ms(ts: str) -> int:
    ts = ts.split("+")[0].split(".")[0].strip()
    return int(datetime.fromisoformat(ts).replace(tzinfo=timezone.utc).timestamp() * 1000)


def pattern_id(p: str) -> int:
    return 0 if p == "B_FLAT_TOP" else 1


def arr(name: str, vals: list) -> str:
    return f"var {name} = array.from({', '.join(str(v) for v in vals)})"


def main() -> None:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    trades = [t for t in rows if t.get("exit_time")][-40:]

    L = []
    L.append("//@version=6")
    L.append("// NAS100 Pattern B/D last 40 trades — Asia+London+mom6, TP=3R, BE@2R")
    L.append("// Box colour: Blue=Pattern B, Orange=Pattern D")
    L.append('indicator("NAS100 PatBD Last 40 Trades (TP3R BE2R)", overlay=true,')
    L.append("          max_labels_count=500, max_lines_count=500, max_boxes_count=500)")
    L.append("")

    L.append(arr("_sts",  [to_ms(t["signal_time"]) for t in trades]))
    L.append(arr("_ets",  [to_ms(t["entry_time"])  for t in trades]))
    L.append(arr("_xts",  [to_ms(t["exit_time"])   for t in trades]))
    L.append(arr("_epx",  [float(t["entry"])        for t in trades]))
    L.append(arr("_sl",   [float(t["sl"])            for t in trades]))
    L.append(arr("_tp",   [float(t["tp"])            for t in trades]))
    L.append(arr("_pnl",  [float(t["pnl_r"])         for t in trades]))
    L.append(arr("_pat",  [pattern_id(t["pattern"])  for t in trades]))
    L.append("")

    L.append("pat_col(p) => p == 0 ? #2196F3 : #FF9800")
    L.append("")

    L.append("if barstate.islast")
    L.append("    n = array.size(_ets)")
    L.append("    for i = 0 to n - 1")
    L.append("        st  = array.get(_sts, i)")
    L.append("        et  = array.get(_ets, i)")
    L.append("        xt  = array.get(_xts, i)")
    L.append("        ep  = array.get(_epx, i)")
    L.append("        sl  = array.get(_sl,  i)")
    L.append("        tp  = array.get(_tp,  i)")
    L.append("        pnl = array.get(_pnl, i)")
    L.append("        pc  = pat_col(array.get(_pat, i))")
    L.append("        win = pnl > 0.0")
    L.append("        be  = pnl == 0.0")
    L.append("")
    L.append("        exit_col = win ? color.new(#4CAF50, 0) : be ? color.new(#FF9800, 0) : color.new(#F44336, 0)")
    L.append("")
    L.append("        // Box from signal bar to exit, coloured by pattern")
    L.append("        box.new(st, tp, xt, sl,")
    L.append("                xloc=xloc.bar_time,")
    L.append("                bgcolor=color.new(pc, 88),")
    L.append("                border_color=color.new(pc, 50),")
    L.append("                border_width=1)")
    L.append("")
    L.append("        // Entry label")
    L.append('        pat_txt = array.get(_pat, i) == 0 ? "PatB" : "PatD"')
    L.append("        label.new(et, ep,")
    L.append("                  text=pat_txt,")
    L.append("                  xloc=xloc.bar_time,")
    L.append("                  style=label.style_label_upper_left,")
    L.append("                  color=color.new(pc, 20),")
    L.append("                  textcolor=color.white, size=size.small)")
    L.append("")
    L.append("        // Exit label")
    L.append('        res_txt = win ? "WIN +3R" : be ? "BE 0R" : "LOSS -1R"')
    L.append("        label.new(xt, win ? tp : be ? ep : sl,")
    L.append("                  text=res_txt,")
    L.append("                  xloc=xloc.bar_time,")
    L.append("                  style=label.style_label_left,")
    L.append("                  color=exit_col,")
    L.append("                  textcolor=color.white, size=size.small)")
    L.append("")
    L.append("        // Entry line")
    L.append("        line.new(et, ep, xt, ep, xloc=xloc.bar_time, color=color.new(pc, 40), width=1)")
    L.append("")
    L.append("        // SL line")
    L.append("        line.new(et, sl, xt, sl, xloc=xloc.bar_time,")
    L.append("                 color=color.new(#F44336, 50), style=line.style_dashed)")
    L.append("")
    L.append("        // TP line")
    L.append("        line.new(et, tp, xt, tp, xloc=xloc.bar_time,")
    L.append("                 color=color.new(#4CAF50, 50), style=line.style_dashed)")

    script = "\n".join(L)
    OUT_PATH.write_text(script, encoding="utf-8")
    print(f"Written: {OUT_PATH}")
    print(f"Lines: {script.count(chr(10))}")

    print("\nTrades included:")
    for t in trades:
        print(f"  {t['date']}  {t['pattern']:<20}  {float(t['pnl_r']):+.1f}R  {t['exit_reason']}")


if __name__ == "__main__":
    main()
