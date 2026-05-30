"""Pre-execution risk checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from execution.position_sizer import SymbolMeta, calculate_lot_size
from strategy import skip_reasons as reasons


@dataclass(frozen=True, slots=True)
class RiskConfig:
    risk_per_trade_percent: float = 0.5
    max_daily_loss_percent: float = 2.0
    max_open_positions: int = 2
    max_trades_per_symbol_per_day: int = 1
    max_total_trades_per_day: int = 3
    min_rr: float = 3.0


@dataclass(frozen=True, slots=True)
class RiskContext:
    account_balance: float
    daily_loss_percent: float
    open_positions: int
    symbol_trades_today: int
    total_trades_today: int


@dataclass(frozen=True, slots=True)
class RiskDecision:
    approved: bool
    lot_size: float | None = None
    skip_reason: str | None = None


def evaluate_risk(
    entry_signal: Mapping[str, float | str],
    symbol_meta: SymbolMeta,
    context: RiskContext,
    config: RiskConfig | None = None,
) -> RiskDecision:
    cfg = config or RiskConfig()
    if float(entry_signal["planned_rr"]) < cfg.min_rr:
        return RiskDecision(False, skip_reason=reasons.SKIP_RR_BELOW_MINIMUM)
    if context.daily_loss_percent >= cfg.max_daily_loss_percent:
        return RiskDecision(False, skip_reason=reasons.SKIP_DAILY_LOSS_LIMIT)
    if context.open_positions >= cfg.max_open_positions:
        return RiskDecision(False, skip_reason=reasons.SKIP_MAX_OPEN_POSITIONS)
    if context.symbol_trades_today >= cfg.max_trades_per_symbol_per_day:
        return RiskDecision(False, skip_reason=reasons.SKIP_MAX_SYMBOL_TRADES_REACHED)

    lot = calculate_lot_size(
        context.account_balance,
        cfg.risk_per_trade_percent,
        float(entry_signal["entry_price"]),
        float(entry_signal["sl"]),
        symbol_meta,
    )
    if lot < symbol_meta.volume_min:
        return RiskDecision(False, lot, reasons.SKIP_LOT_SIZE_TOO_SMALL)
    if lot > symbol_meta.volume_max:
        return RiskDecision(False, lot, reasons.SKIP_LOT_SIZE_TOO_LARGE)
    return RiskDecision(True, lot)
