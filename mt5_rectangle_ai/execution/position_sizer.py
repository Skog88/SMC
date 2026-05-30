"""MT5-style position sizing calculations."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Any


@dataclass(frozen=True, slots=True)
class SymbolMeta:
    symbol: str
    trade_tick_size: float
    trade_tick_value: float
    volume_min: float
    volume_max: float
    volume_step: float
    digits: int
    point: float


def symbol_meta_from_mcp(info: dict[str, Any]) -> SymbolMeta:
    point = float(info["point"])
    pip_value = float(info.get("pip_value_per_lot", 0.0))
    return SymbolMeta(
        symbol=str(info["symbol"]),
        trade_tick_size=point,
        trade_tick_value=pip_value / 10 if pip_value else point,
        volume_min=float(info["min_lot"]),
        volume_max=float(info["max_lot"]),
        volume_step=float(info["lot_step"]),
        digits=int(info["digits"]),
        point=point,
    )


def round_down_to_step(value: float, step: float) -> float:
    if step <= 0:
        raise ValueError("volume step must be positive")
    return floor(value / step) * step


def calculate_lot_size(
    account_balance: float,
    risk_percent: float,
    entry_price: float,
    sl: float,
    symbol_meta: SymbolMeta,
) -> float:
    price_distance = abs(entry_price - sl)
    if price_distance <= 0:
        raise ValueError("SL distance must be positive")
    ticks_to_sl = price_distance / symbol_meta.trade_tick_size
    money_risk_per_1_lot = ticks_to_sl * symbol_meta.trade_tick_value
    if money_risk_per_1_lot <= 0:
        raise ValueError("money risk per lot must be positive")
    risk_money = account_balance * (risk_percent / 100)
    raw_lot = risk_money / money_risk_per_1_lot
    lot = round_down_to_step(raw_lot, symbol_meta.volume_step)
    return round(lot, 8)
