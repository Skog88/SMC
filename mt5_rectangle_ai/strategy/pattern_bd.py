"""
Pattern B/D detection - copied from C:/ST.DEMO/monitor.py

Pattern B  — Flat Top Breakout
Pattern D  — First Pullback Higher High / Bull Flag (buffered: entry at next bar open)

Pure detection functions only — no broker dependency.
check_entry_signal() accepts a session DataFrame (5-min bars, uppercase OHLCV cols,
time-zone-aware datetime index) instead of an IBKR broker + ticker.

Constants mirror C:/ST.DEMO/config.py exactly.
"""

from __future__ import annotations

import pandas as pd

# ─── Constants (from C:\ST.DEMO\config.py) ───────────────────────────────────
MIN_RR_RATIO         = 2.0
FLAT_TOP_TOLERANCE   = 0.003
FLAT_TOP_MIN_TOUCHES = 2
MIN_PULLBACK_CANDLES = 2
MAX_PULLBACK_CANDLES = 4


# ─── Helpers ──────────────────────────────────────────────────────────────────

def detect_swing_high(df: pd.DataFrame, lookback: int = 10) -> float | None:
    if len(df) < 3:
        return None
    highs = df["High"].values[-lookback:]
    for i in range(len(highs) - 2, 0, -1):
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            return round(float(highs[i]), 2)
    return None

def count_consecutive_red(df: pd.DataFrame) -> int:
    count = 0
    closes, opens = df["Close"].values, df["Open"].values
    for i in range(len(closes) - 1, -1, -1):
        if closes[i] < opens[i]:
            count += 1
        else:
            break
    return count

def find_flat_top(df: pd.DataFrame, tolerance: float = 0.003, min_touches: int = 2) -> float | None:
    if len(df) < min_touches + 1:
        return None
    highs = df["High"].values[-(min_touches + 4):]
    if len(highs) < min_touches:
        return None
    for ref in highs:
        if sum(1 for h in highs if abs(h - ref) / ref <= tolerance) >= min_touches:
            return round(float(ref), 2)
    return None

def find_pullback_low(df: pd.DataFrame) -> float | None:
    """Lowest low of the most recent red-candle pullback sequence in df."""
    closes = df["Close"].values
    opens  = df["Open"].values
    lows   = df["Low"].values
    n = len(closes)
    i = n - 1
    while i >= 0 and closes[i] < opens[i]:
        i -= 1
    pb_start = i + 1
    if pb_start >= n:
        return None
    return round(float(lows[pb_start:n].min()), 8)

def is_first_pullback(df: pd.DataFrame) -> bool:
    closes, opens = df["Close"].values, df["Open"].values
    n = len(closes)
    if n < 3:
        return False
    i = n - 1
    while i >= 0 and closes[i] < opens[i]:
        i -= 1
    while i >= 0 and closes[i] >= opens[i]:
        i -= 1
    return i <= 0


# ── Pattern D helpers ─────────────────────────────────────────────────────────

def _session_to_patd_df(session: pd.DataFrame) -> pd.DataFrame:
    """Convert session DataFrame (uppercase cols, time index) to PatD format."""
    out = session.copy().reset_index()
    out.columns = ["datetime"] + [c.lower() for c in session.columns]
    out["datetime"] = pd.to_datetime(out["datetime"])
    return out


def _detect_pattern_d(df: pd.DataFrame) -> list[dict]:
    """
    Pattern D — Bull Flag.
    Checks only the last bar of df as the candidate signal bar.
    Scans right-to-left for the pullback immediately before it.
    Returns a list of 0 or 1 signals.
    """
    n = len(df)
    if n < 4:
        return []

    opens  = df["open"].values.astype(float)
    closes = df["close"].values.astype(float)
    highs  = df["high"].values.astype(float)
    lows   = df["low"].values.astype(float)
    times  = pd.to_datetime(df["datetime"])

    k = n - 1  # signal bar candidate = last bar

    # Must be green and make a higher high than the bar before it
    if not (closes[k] > opens[k] and highs[k] > highs[k - 1]):
        return []

    # Find pullback immediately before k: walk backwards from k-1
    # counting bars where each bar's low < the prior bar's low
    pb_end = k - 1  # last bar of pullback
    pb_start = pb_end
    while pb_start > 0 and lows[pb_start] < lows[pb_start - 1]:
        pb_start -= 1

    pb_len = pb_end - pb_start + 1
    if pb_len < 2:
        return []

    # Stop = lowest low from pullback start through signal bar
    pb_low = float(lows[pb_start: k + 1].min())

    entry_bar = k + 1
    entry = round(float(opens[entry_bar]), 2) if entry_bar < n \
            else round(float(closes[k]), 2)
    stop  = round(pb_low, 2)

    if entry <= stop:
        return []

    stop_dist     = round((entry - stop) / entry * 100, 2)
    t_idx         = min(entry_bar, n - 1)
    min_from_open = int((times.iloc[t_idx] - times.iloc[0]).total_seconds() / 60)
    target        = round(entry + 2 * (entry - stop), 2)

    return [{
        "entry":         entry,
        "stop":          stop,
        "stop_dist":     stop_dist,
        "min_from_open": min_from_open,
        "_signal_bar":   k,
        "_entry_bar":    entry_bar,
        "_target":       target,
    }]


# ─── Main Detection ───────────────────────────────────────────────────────────

def check_entry_signal(session: pd.DataFrame) -> dict | None:
    """
    Accepts a session DataFrame: uppercase OHLCV columns, time-zone-aware
    datetime index (same format as get_5min_bars in monitor.py).
    Returns a signal dict or None.
    """
    if session.empty or len(session) < 4:
        return None

    latest       = session.iloc[-1]
    latest_close = float(latest["Close"])
    latest_open  = float(latest["Open"])
    latest_vol   = float(latest["Volume"])

    if latest_close <= latest_open:
        return None

    avg_vol   = float(session["Volume"].mean())
    vol_ratio = latest_vol / avg_vol if avg_vol > 0 else 0
    prior     = session.iloc[:-1]

    # ── Pattern B: Flat Top Breakout ──────────────────────────────────────────
    flat_top = find_flat_top(prior, tolerance=FLAT_TOP_TOLERANCE, min_touches=FLAT_TOP_MIN_TOUCHES)

    session_high = float(prior["High"].max())

    if (
        flat_top is not None
        and flat_top >= session_high * (1 - FLAT_TOP_TOLERANCE)
        and latest_close > flat_top
        and latest["High"] > float(prior.iloc[-1]["High"])
        and is_first_pullback(prior)
        and vol_ratio >= 1.0
    ):
        pb_low     = find_pullback_low(prior)
        stop_price = pb_low if pb_low is not None else round(flat_top - (flat_top * 0.005), 8)
        risk       = latest_close - stop_price
        target     = round(latest_close + (risk * 2.0), 2)
        rr         = round((target - latest_close) / risk, 2) if risk > 0 else 0

        if rr >= MIN_RR_RATIO and risk > 0:
            return {
                "pattern":      "B_FLAT_TOP",
                "entry_price":  round(latest_close, 2),
                "stop_price":   stop_price,
                "target_price": target,
                "rr_ratio":     rr,
                "flat_top":     flat_top,
                "vol_ratio":    round(vol_ratio, 2),
                "reason": (
                    f"Flat top break at ${flat_top} | "
                    f"Stop: ${stop_price} | Target: ${target} | R:R {rr}"
                ),
            }

    # ── Pattern D: First Pullback Higher High ─────────────────────────────────
    patd_df      = _session_to_patd_df(session)
    patd_signals = _detect_pattern_d(patd_df)

    if patd_signals:
        s = patd_signals[-1]
        if s["_signal_bar"] == len(patd_df) - 1:
            entry_price = round(float(session["Close"].iloc[-1]), 2)
            stop_price  = round(s["stop"], 2)
            risk        = entry_price - stop_price
            if risk > 0:
                target = round(entry_price + 2 * risk, 2)
                rr     = round((target - entry_price) / risk, 2)
                if rr >= MIN_RR_RATIO:
                    return {
                        "pattern":           "D_FIRST_PULLBACK",
                        "entry_price":       entry_price,
                        "stop_price":        stop_price,
                        "target_price":      target,
                        "rr_ratio":          rr,
                        "stop_dist_pct":     s["stop_dist"],
                        "min_from_open":     s["min_from_open"],
                        "vol_ratio":         round(vol_ratio, 2),
                        "_signal_bar_time":  session.index[s["_signal_bar"]],
                        "reason": (
                            f"PatD first pullback: stop=${stop_price} | "
                            f"entry~${entry_price} | target=${target} | "
                            f"R:R {rr} | dist {s['stop_dist']:.1f}% | "
                            f"{s['min_from_open']} min from open"
                        ),
                    }

    return None
