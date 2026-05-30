"""Render clean candlestick images for Claude vision review."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd

from core.candle_builder import Candle


def render_sweep_chart(
    candles: list[Candle],
    sweep_candle: Candle,
    level_price: float,
    rectangle_high: float,
    rectangle_low: float,
    direction: str,
    output_path: Path,
) -> Path:
    """Render the last 60 M15 candles and annotate the sweep zone."""
    if not candles:
        raise ValueError("candles cannot be empty")

    visible = candles[-60:]
    frame = pd.DataFrame(
        {
            "Open": [c.open for c in visible],
            "High": [c.high for c in visible],
            "Low": [c.low for c in visible],
            "Close": [c.close for c in visible],
        },
        index=pd.DatetimeIndex([c.time for c in visible]),
    )

    style = mpf.make_mpf_style(
        base_mpf_style="nightclouds",
        marketcolors=mpf.make_marketcolors(up="#26a69a", down="#ef5350", inherit=True),
        facecolor="#0f1117",
        figcolor="#0f1117",
        gridcolor="#222630",
        gridstyle="-",
    )
    fig, axes = mpf.plot(
        frame,
        type="candle",
        style=style,
        volume=False,
        axisoff=True,
        returnfig=True,
        figsize=(12, 6),
        tight_layout=True,
        show_nontrading=True,
        warn_too_much_data=1000,
    )
    ax = axes[0]
    ax.axhline(level_price, color="#f5c542", linestyle="--", linewidth=1.2, alpha=0.95)

    sweep_x = mdates.date2num(sweep_candle.time)
    end_x = mdates.date2num(visible[-1].time)
    width = max(end_x - sweep_x, 1 / 96)
    zone_color = "#26a69a" if direction == "long" else "#ef5350"
    zone = patches.Rectangle(
        (sweep_x, rectangle_low),
        width,
        rectangle_high - rectangle_low,
        linewidth=1.2,
        edgecolor=zone_color,
        facecolor=zone_color,
        alpha=0.18,
    )
    ax.add_patch(zone)

    candle_width = 10 / (24 * 60)
    highlight = patches.Rectangle(
        (sweep_x - candle_width / 2, sweep_candle.low),
        candle_width,
        sweep_candle.high - sweep_candle.low,
        linewidth=2.0,
        edgecolor=zone_color,
        facecolor="none",
        alpha=1.0,
    )
    ax.add_patch(highlight)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", pad_inches=0.03, facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path
