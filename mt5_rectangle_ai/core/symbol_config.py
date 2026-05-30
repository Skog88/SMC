"""Symbol classification helpers used by SL and spread configuration."""

from __future__ import annotations


FOREX_SUFFIXES = ("USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD")


def classify_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if normalized.startswith("XAU") or normalized.startswith("XAG"):
        return "metals"
    if any(token in normalized for token in ("US100", "NAS", "SPX", "US30", "GER40")):
        return "indices"
    if any(token in normalized for token in ("BTC", "ETH", "SOL", "CRYPTO")):
        return "crypto"
    if len(normalized) >= 6 and normalized[:3] in FOREX_SUFFIXES and normalized[3:6] in FOREX_SUFFIXES:
        return "forex"
    return "default"


def get_symbol_setting(settings: dict, symbol: str, default_key: str = "default"):
    return settings.get(symbol, settings.get(classify_symbol(symbol), settings.get(default_key)))
