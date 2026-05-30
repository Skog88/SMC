"""
mt5_mcp_server_old.py  —  RECOVERY SNAPSHOT
Claude Code → MT5 → Fusion Markets

This is the MCP server state that produced GBPUSD_no_buffer_plus8R_trades.csv.

KEY DIFFERENCE from the live server (C:/mt5-mcp/mt5_mcp_server.py):
  get_candles uses:
      datetime.datetime.fromtimestamp(r["time"])    ← machine local time (UTC+2)
  instead of the corrected:
      datetime.datetime.utcfromtimestamp(r["time"]) - _BROKER_OFFSET  ← true UTC

Combined with broker timestamps being UTC+3, this means candle times returned
here are UTC+5 (3h broker + 2h machine).  The recovery backtest uses
datetime.now() (also UTC+2) for its window, so the window and candle timestamps
are internally consistent — but both are shifted 5h ahead of true UTC.

DO NOT use this server for live trading or any new development.
Run it only via mechanical_backtest_plus8R.py for recovery comparison purposes.
"""

import json
import logging
import asyncio
import datetime
import time
from typing import Any
import MetaTrader5 as mt5
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("mt5-mcp-old")

server = Server("mt5-fusion-markets-old")

MAGIC = 20250419

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1,
}


def connect() -> bool:
    return mt5.initialize()


def err() -> str:
    code, msg = mt5.last_error()
    return f"MT5 error {code}: {msg}"


def get_filling(symbol: str) -> int:
    info = mt5.symbol_info(symbol)
    fm = info.filling_mode if info else 2
    return (mt5.ORDER_FILLING_FOK if fm & 1
            else mt5.ORDER_FILLING_IOC if fm & 2
            else mt5.ORDER_FILLING_RETURN)


def close_pos(pos) -> tuple[bool, str]:
    close_type  = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    tick        = mt5.symbol_info_tick(pos.symbol)
    close_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
    result = mt5.order_send({
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       pos.symbol,
        "volume":       pos.volume,
        "type":         close_type,
        "position":     pos.ticket,
        "price":        close_price,
        "deviation":    20,
        "magic":        MAGIC,
        "comment":      "Claude Code close",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": get_filling(pos.symbol),
    })
    ok = result and result.retcode == mt5.TRADE_RETCODE_DONE
    return ok, (str(result.retcode) if result else "None")


# ── Tools ─────────────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [

        types.Tool(
            name="get_account",
            description="Get account balance, equity, margin, free margin and open P&L.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),

        types.Tool(
            name="get_price",
            description="Get current bid/ask price for a symbol. E.g. EURUSD, XAUUSD, US30.",
            inputSchema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        ),

        types.Tool(
            name="get_positions",
            description="List all currently open positions with P&L.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),

        types.Tool(
            name="place_order",
            description=(
                "Place a market BUY or SELL order on Fusion Markets. "
                "Provide symbol, direction (buy/sell), volume in lots. "
                "Optionally provide sl (stop loss price) and tp (take profit price)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol":    {"type": "string", "description": "e.g. EURUSD"},
                    "direction": {"type": "string", "enum": ["buy", "sell"]},
                    "volume":    {"type": "number", "description": "Lot size e.g. 0.1"},
                    "sl":        {"type": "number", "description": "Stop loss price (optional)"},
                    "tp":        {"type": "number", "description": "Take profit price (optional)"},
                },
                "required": ["symbol", "direction", "volume"],
            },
        ),

        types.Tool(
            name="close_position",
            description="Close one open position by its ticket number.",
            inputSchema={
                "type": "object",
                "properties": {"ticket": {"type": "integer"}},
                "required": ["ticket"],
            },
        ),

        types.Tool(
            name="close_all",
            description="Close ALL open positions. Optionally filter by symbol.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Optional: close only this symbol"}
                },
                "required": [],
            },
        ),

        types.Tool(
            name="modify_position",
            description="Move the stop loss and/or take profit of an open position.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {"type": "integer"},
                    "sl":     {"type": "number", "description": "New stop loss price"},
                    "tp":     {"type": "number", "description": "New take profit price"},
                },
                "required": ["ticket"],
            },
        ),

        types.Tool(
            name="get_history",
            description="Get closed trade history for the last N days.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Days to look back (default 7)"}
                },
                "required": [],
            },
        ),

        types.Tool(
            name="place_pending",
            description=(
                "Place a pending limit or stop order. "
                "Types: buy_limit, sell_limit, buy_stop, sell_stop. "
                "Price is the trigger/entry price. Optionally provide sl, tp, and expiry."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol":     {"type": "string"},
                    "order_type": {"type": "string", "enum": ["buy_limit", "sell_limit", "buy_stop", "sell_stop"]},
                    "volume":     {"type": "number"},
                    "price":      {"type": "number"},
                    "sl":         {"type": "number"},
                    "tp":         {"type": "number"},
                    "expiry":     {"type": "string", "description": "Optional YYYY-MM-DD HH:MM"},
                },
                "required": ["symbol", "order_type", "volume", "price"],
            },
        ),

        types.Tool(
            name="get_pending_orders",
            description="List all pending (unfilled) limit and stop orders.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),

        types.Tool(
            name="cancel_order",
            description="Cancel a single pending order by ticket number.",
            inputSchema={
                "type": "object",
                "properties": {"ticket": {"type": "integer"}},
                "required": ["ticket"],
            },
        ),

        types.Tool(
            name="get_candles",
            description=(
                "Fetch OHLCV candlestick data for a symbol and timeframe. "
                "Timeframes: M1 M5 M15 M30 H1 H4 D1 W1 MN1. "
                "Returns the last N candles (default 50)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol":    {"type": "string", "description": "e.g. XAUUSD"},
                    "timeframe": {"type": "string", "description": "e.g. H1"},
                    "count":     {"type": "integer", "description": "Number of candles (default 50)"},
                },
                "required": ["symbol", "timeframe"],
            },
        ),

        types.Tool(
            name="get_symbols",
            description="List all available trading symbols on the account. Optionally filter by a search string.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {"type": "string", "description": "Optional search string e.g. 'XAU' or 'USD'"}
                },
                "required": [],
            },
        ),

        types.Tool(
            name="symbol_info",
            description="Get detailed contract info for a symbol: pip value, contract size, min/max lot, spread.",
            inputSchema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        ),

        types.Tool(
            name="partial_close",
            description="Close part of an open position. Specify ticket and the volume to close.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {"type": "integer"},
                    "volume": {"type": "number", "description": "Lots to close (must be less than full position size)"},
                },
                "required": ["ticket", "volume"],
            },
        ),

        types.Tool(
            name="move_to_breakeven",
            description="Move the stop loss of an open position to its entry price (breakeven).",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {"type": "integer"},
                    "offset_pips": {"type": "number", "description": "Optional pip buffer above/below entry (default 0)"},
                },
                "required": ["ticket"],
            },
        ),

        types.Tool(
            name="trailing_stop",
            description=(
                "Set a trailing stop on an open position by pip distance. "
                "Updates the SL to trail the current price by the given pips."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {"type": "integer"},
                    "pips":   {"type": "number", "description": "Trail distance in pips"},
                },
                "required": ["ticket", "pips"],
            },
        ),

        types.Tool(
            name="scale_in",
            description="Add to an existing open position (same symbol and direction).",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {"type": "integer", "description": "Existing position ticket to scale into"},
                    "volume": {"type": "number", "description": "Additional lots to add"},
                    "sl":     {"type": "number", "description": "New SL for all positions on this symbol (optional)"},
                    "tp":     {"type": "number", "description": "New TP for all positions on this symbol (optional)"},
                },
                "required": ["ticket", "volume"],
            },
        ),

        types.Tool(
            name="daily_pnl",
            description="Get today's realised P&L plus current unrealised P&L.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),

        types.Tool(
            name="account_stats",
            description=(
                "Calculate trading statistics from history: win rate, profit factor, "
                "average win, average loss, best and worst trade."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Days to analyse (default 30)"}
                },
                "required": [],
            },
        ),

        types.Tool(
            name="risk_check",
            description=(
                "Calculate the correct lot size for a trade given an account risk percentage and stop loss distance. "
                "Returns recommended lot size, dollar risk, and pip value."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol":       {"type": "string"},
                    "sl_pips":      {"type": "number", "description": "Stop loss distance in pips"},
                    "risk_percent": {"type": "number", "description": "Risk as % of account balance e.g. 1.0"},
                },
                "required": ["symbol", "sl_pips", "risk_percent"],
            },
        ),

        types.Tool(
            name="cancel_all_pending",
            description="Cancel all pending orders at once. Optionally filter by symbol.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Optional: cancel only orders on this symbol"}
                },
                "required": [],
            },
        ),

        types.Tool(
            name="close_all_in_profit",
            description="Close all positions that are currently in profit. Optionally filter by symbol.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Optional: only this symbol"}
                },
                "required": [],
            },
        ),

        types.Tool(
            name="close_all_in_loss",
            description="Close all positions that are currently at a loss. Optionally filter by symbol.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Optional: only this symbol"}
                },
                "required": [],
            },
        ),
    ]


# ── Tool handlers ─────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:

    def text(s: str) -> list[types.TextContent]:
        return [types.TextContent(type="text", text=s)]

    if not connect():
        return text(f"❌ Cannot connect to MT5. Is the terminal open and logged in? {err()}")

    # ── get_account ───────────────────────────────────────────────────────────
    if name == "get_account":
        info = mt5.account_info()
        if not info:
            return text(f"❌ {err()}")
        return text(json.dumps({
            "login":       info.login,
            "broker":      info.company,
            "currency":    info.currency,
            "balance":     round(info.balance,    2),
            "equity":      round(info.equity,     2),
            "margin":      round(info.margin,     2),
            "free_margin": round(info.margin_free,2),
            "open_pnl":    round(info.profit,     2),
            "leverage":    f"1:{info.leverage}",
        }, indent=2))

    # ── get_price ─────────────────────────────────────────────────────────────
    elif name == "get_price":
        symbol = arguments["symbol"].upper()
        tick   = mt5.symbol_info_tick(symbol)
        if not tick:
            return text(f"❌ Symbol {symbol} not found or not in Market Watch. {err()}")
        info   = mt5.symbol_info(symbol)
        spread = round((tick.ask - tick.bid) / (info.point * 10), 1) if info else "?"
        return text(json.dumps({
            "symbol": symbol,
            "bid":    tick.bid,
            "ask":    tick.ask,
            "spread": f"{spread} pips",
        }, indent=2))

    # ── get_positions ─────────────────────────────────────────────────────────
    elif name == "get_positions":
        positions = mt5.positions_get()
        if not positions:
            return text("No open positions.")
        result = []
        for p in positions:
            result.append({
                "ticket":        p.ticket,
                "symbol":        p.symbol,
                "direction":     "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume":        p.volume,
                "open_price":    p.price_open,
                "current_price": p.price_current,
                "sl":            p.sl or None,
                "tp":            p.tp or None,
                "pnl":           round(p.profit, 2),
                "comment":       p.comment,
            })
        total_pnl = round(sum(p["pnl"] for p in result), 2)
        return text(json.dumps({"positions": result, "total_pnl": total_pnl}, indent=2))

    # ── place_order ───────────────────────────────────────────────────────────
    elif name == "place_order":
        symbol    = arguments["symbol"].upper()
        direction = arguments["direction"].lower()
        volume    = float(arguments["volume"])
        sl        = float(arguments.get("sl", 0.0))
        tp        = float(arguments.get("tp", 0.0))

        if not mt5.symbol_select(symbol, True):
            return text(f"❌ Symbol {symbol} not available on your account.")

        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if not info or not tick:
            return text(f"❌ Could not get price for {symbol}.")

        order_type = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
        price      = tick.ask if direction == "buy" else tick.bid

        for attempt in range(3):
            result = mt5.order_send({
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       symbol,
                "volume":       volume,
                "type":         order_type,
                "price":        price,
                "sl":           sl,
                "tp":           tp,
                "deviation":    20,
                "magic":        MAGIC,
                "comment":      "Claude Code",
                "type_time":    mt5.ORDER_TIME_GTC,
                "type_filling": get_filling(symbol),
            })
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                log.info("Order placed: %s %s %s @ %s", direction, volume, symbol, result.price)
                return text(json.dumps({
                    "status":    "✅ Order placed",
                    "ticket":    result.order,
                    "symbol":    symbol,
                    "direction": direction.upper(),
                    "volume":    volume,
                    "price":     result.price,
                    "sl":        sl or None,
                    "tp":        tp or None,
                }, indent=2))
            elif result and result.retcode in {10004, 10020, 10021}:
                time.sleep(0.5)
                tick  = mt5.symbol_info_tick(symbol)
                price = tick.ask if direction == "buy" else tick.bid
                continue
            else:
                code = result.retcode if result else "None"
                msg  = result.comment if result else err()
                return text(f"❌ Order failed — retcode {code}: {msg}")

        return text("❌ Order failed after 3 attempts (requote/price change).")

    # ── close_position ────────────────────────────────────────────────────────
    elif name == "close_position":
        ticket    = int(arguments["ticket"])
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return text(f"❌ No open position with ticket {ticket}.")
        ok, code = close_pos(positions[0])
        return text(f"✅ Ticket {ticket} closed." if ok else f"❌ Close failed — retcode {code}")

    # ── close_all ─────────────────────────────────────────────────────────────
    elif name == "close_all":
        symbol_filter = arguments.get("symbol", "").upper() or None
        positions     = (mt5.positions_get(symbol=symbol_filter)
                         if symbol_filter else mt5.positions_get())
        if not positions:
            return text("No open positions to close.")
        lines = []
        for pos in positions:
            ok, code = close_pos(pos)
            lines.append(f"{'✅' if ok else '❌'} Ticket {pos.ticket} {pos.symbol} {'closed' if ok else 'failed: ' + code}")
        return text("\n".join(lines))

    # ── modify_position ───────────────────────────────────────────────────────
    elif name == "modify_position":
        ticket = int(arguments["ticket"])
        sl     = float(arguments.get("sl", 0.0))
        tp     = float(arguments.get("tp", 0.0))

        if not mt5.positions_get(ticket=ticket):
            return text(f"❌ No open position with ticket {ticket}.")

        result = mt5.order_send({
            "action":   mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl":       sl,
            "tp":       tp,
        })
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return text(f"✅ Ticket {ticket} modified — SL: {sl or 'removed'}, TP: {tp or 'removed'}")
        else:
            code = result.retcode if result else "None"
            return text(f"❌ Modify failed — retcode {code}")

    # ── get_history ───────────────────────────────────────────────────────────
    elif name == "get_history":
        days  = int(arguments.get("days", 7))
        now   = datetime.datetime.now()
        start = now - datetime.timedelta(days=days)
        deals = mt5.history_deals_get(start, now)
        if not deals:
            return text(f"No closed trades in the last {days} days.")

        trades = []
        for d in deals:
            if d.entry in (mt5.DEAL_ENTRY_IN, mt5.DEAL_ENTRY_OUT) and d.symbol:
                trades.append({
                    "ticket":    d.ticket,
                    "time":      datetime.datetime.fromtimestamp(d.time).strftime("%Y-%m-%d %H:%M"),
                    "symbol":    d.symbol,
                    "direction": "BUY" if d.type == mt5.DEAL_TYPE_BUY else "SELL",
                    "volume":    d.volume,
                    "price":     d.price,
                    "pnl":       round(d.profit, 2),
                })

        total = round(sum(t["pnl"] for t in trades), 2)
        return text(json.dumps({
            "period_days":  days,
            "total_trades": len(trades),
            "total_pnl":    total,
            "trades":       trades,
        }, indent=2))

    # ── place_pending ─────────────────────────────────────────────────────────
    elif name == "place_pending":
        symbol     = arguments["symbol"].upper()
        order_type = arguments["order_type"].lower()
        volume     = float(arguments["volume"])
        price      = float(arguments["price"])
        sl         = float(arguments.get("sl", 0.0))
        tp         = float(arguments.get("tp", 0.0))
        expiry_str = arguments.get("expiry", "")

        if not mt5.symbol_select(symbol, True):
            return text(f"❌ Symbol {symbol} not available on your account.")

        type_map = {
            "buy_limit":  mt5.ORDER_TYPE_BUY_LIMIT,
            "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT,
            "buy_stop":   mt5.ORDER_TYPE_BUY_STOP,
            "sell_stop":  mt5.ORDER_TYPE_SELL_STOP,
        }
        if order_type not in type_map:
            return text(f"❌ Unknown order type: {order_type}")

        request = {
            "action":       mt5.TRADE_ACTION_PENDING,
            "symbol":       symbol,
            "volume":       volume,
            "type":         type_map[order_type],
            "price":        price,
            "sl":           sl,
            "tp":           tp,
            "deviation":    20,
            "magic":        MAGIC,
            "comment":      "Claude Code pending",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": get_filling(symbol),
        }

        if expiry_str:
            try:
                exp_dt = datetime.datetime.strptime(expiry_str, "%Y-%m-%d %H:%M")
                request["type_time"]  = mt5.ORDER_TIME_SPECIFIED
                request["expiration"] = int(exp_dt.timestamp())
            except ValueError:
                return text("❌ Invalid expiry format. Use YYYY-MM-DD HH:MM")

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return text(json.dumps({
                "status":     "✅ Pending order placed",
                "ticket":     result.order,
                "symbol":     symbol,
                "order_type": order_type.upper(),
                "volume":     volume,
                "price":      price,
                "sl":         sl or None,
                "tp":         tp or None,
            }, indent=2))
        else:
            code = result.retcode if result else "None"
            msg  = result.comment if result else err()
            return text(f"❌ Pending order failed — retcode {code}: {msg}")

    # ── get_pending_orders ────────────────────────────────────────────────────
    elif name == "get_pending_orders":
        orders = mt5.orders_get()
        if not orders:
            return text("No pending orders.")
        type_names = {
            mt5.ORDER_TYPE_BUY_LIMIT:  "BUY LIMIT",
            mt5.ORDER_TYPE_SELL_LIMIT: "SELL LIMIT",
            mt5.ORDER_TYPE_BUY_STOP:   "BUY STOP",
            mt5.ORDER_TYPE_SELL_STOP:  "SELL STOP",
        }
        result = [{
            "ticket":     o.ticket,
            "symbol":     o.symbol,
            "order_type": type_names.get(o.type, str(o.type)),
            "volume":     o.volume_current,
            "price":      o.price_open,
            "sl":         o.sl or None,
            "tp":         o.tp or None,
            "comment":    o.comment,
        } for o in orders]
        return text(json.dumps({"pending_orders": result, "count": len(result)}, indent=2))

    # ── cancel_order ──────────────────────────────────────────────────────────
    elif name == "cancel_order":
        ticket = int(arguments["ticket"])
        result = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return text(f"✅ Pending order {ticket} cancelled.")
        else:
            code = result.retcode if result else "None"
            return text(f"❌ Cancel failed — retcode {code}")

    # ── get_candles ───────────────────────────────────────────────────────────
    # NOTE: This is the OLD behaviour — fromtimestamp() returns machine local
    # time (UTC+2).  Combined with broker UTC+3 storage, candle times are UTC+5.
    elif name == "get_candles":
        symbol    = arguments["symbol"].upper()
        tf_str    = arguments["timeframe"].upper()
        count     = int(arguments.get("count", 50))

        if tf_str not in TIMEFRAMES:
            return text(f"❌ Unknown timeframe '{tf_str}'. Use: {', '.join(TIMEFRAMES)}")

        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAMES[tf_str], 0, count)
        if rates is None or len(rates) == 0:
            return text(f"❌ No candle data for {symbol} {tf_str}. {err()}")

        candles = []
        for r in rates:
            candles.append({
                "time":   datetime.datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M"),
                "open":   round(float(r["open"]),  5),
                "high":   round(float(r["high"]),  5),
                "low":    round(float(r["low"]),   5),
                "close":  round(float(r["close"]), 5),
                "volume": int(r["tick_volume"]),
            })
        return text(json.dumps({
            "symbol": symbol, "timeframe": tf_str,
            "count": len(candles), "candles": candles
        }, indent=2))

    # ── get_symbols ───────────────────────────────────────────────────────────
    elif name == "get_symbols":
        filt    = arguments.get("filter", "").upper()
        symbols = mt5.symbols_get(filt) if filt else mt5.symbols_get()
        if not symbols:
            return text("No symbols found.")
        names = [s.name for s in symbols]
        return text(json.dumps({"count": len(names), "symbols": names}, indent=2))

    # ── symbol_info ───────────────────────────────────────────────────────────
    elif name == "symbol_info":
        symbol = arguments["symbol"].upper()
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
        if not info:
            return text(f"❌ Symbol {symbol} not found. {err()}")
        tick = mt5.symbol_info_tick(symbol)
        spread_pips = round((tick.ask - tick.bid) / (info.point * 10), 1) if tick else "?"
        return text(json.dumps({
            "symbol":          symbol,
            "description":     info.description,
            "currency_base":   info.currency_base,
            "currency_profit": info.currency_profit,
            "contract_size":   info.trade_contract_size,
            "min_lot":         info.volume_min,
            "max_lot":         info.volume_max,
            "lot_step":        info.volume_step,
            "point":           info.point,
            "digits":          info.digits,
            "spread_pips":     spread_pips,
            "pip_value_per_lot": round(info.trade_contract_size * info.point * 10, 4),
        }, indent=2))

    # ── partial_close ─────────────────────────────────────────────────────────
    elif name == "partial_close":
        ticket = int(arguments["ticket"])
        volume = float(arguments["volume"])

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return text(f"❌ No open position with ticket {ticket}.")

        pos = positions[0]
        if volume >= pos.volume:
            return text(f"❌ Volume {volume} must be less than full position size {pos.volume}. Use close_position to close fully.")

        close_type  = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick        = mt5.symbol_info_tick(pos.symbol)
        close_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        result = mt5.order_send({
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       volume,
            "type":         close_type,
            "position":     ticket,
            "price":        close_price,
            "deviation":    20,
            "magic":        MAGIC,
            "comment":      "Claude Code partial close",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": get_filling(pos.symbol),
        })
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            remaining = round(pos.volume - volume, 2)
            return text(f"✅ Partial close: {volume} lots closed at {close_price}. Remaining: {remaining} lots.")
        else:
            code = result.retcode if result else "None"
            return text(f"❌ Partial close failed — retcode {code}")

    # ── move_to_breakeven ─────────────────────────────────────────────────────
    elif name == "move_to_breakeven":
        ticket      = int(arguments["ticket"])
        offset_pips = float(arguments.get("offset_pips", 0.0))

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return text(f"❌ No open position with ticket {ticket}.")

        pos  = positions[0]
        info = mt5.symbol_info(pos.symbol)
        pip  = info.point * 10 if info else 0.0001

        if pos.type == mt5.ORDER_TYPE_BUY:
            new_sl = round(pos.price_open + offset_pips * pip, info.digits if info else 5)
        else:
            new_sl = round(pos.price_open - offset_pips * pip, info.digits if info else 5)

        result = mt5.order_send({
            "action":   mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl":       new_sl,
            "tp":       pos.tp,
        })
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return text(f"✅ Ticket {ticket} SL moved to breakeven ({new_sl}).")
        else:
            code = result.retcode if result else "None"
            return text(f"❌ Breakeven failed — retcode {code}")

    # ── trailing_stop ─────────────────────────────────────────────────────────
    elif name == "trailing_stop":
        ticket = int(arguments["ticket"])
        pips   = float(arguments["pips"])

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return text(f"❌ No open position with ticket {ticket}.")

        pos  = positions[0]
        info = mt5.symbol_info(pos.symbol)
        tick = mt5.symbol_info_tick(pos.symbol)
        if not info or not tick:
            return text(f"❌ Could not get market data for {pos.symbol}.")

        pip    = info.point * 10
        digits = info.digits

        if pos.type == mt5.ORDER_TYPE_BUY:
            new_sl = round(tick.bid - pips * pip, digits)
            if pos.sl and new_sl <= pos.sl:
                return text(f"ℹ️ Trailing SL ({new_sl}) is not better than current SL ({pos.sl}). No change.")
        else:
            new_sl = round(tick.ask + pips * pip, digits)
            if pos.sl and new_sl >= pos.sl:
                return text(f"ℹ️ Trailing SL ({new_sl}) is not better than current SL ({pos.sl}). No change.")

        result = mt5.order_send({
            "action":   mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl":       new_sl,
            "tp":       pos.tp,
        })
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return text(f"✅ Ticket {ticket} trailing SL set to {new_sl} ({pips} pips from current price).")
        else:
            code = result.retcode if result else "None"
            return text(f"❌ Trailing stop failed — retcode {code}")

    # ── scale_in ──────────────────────────────────────────────────────────────
    elif name == "scale_in":
        ticket = int(arguments["ticket"])
        volume = float(arguments["volume"])
        new_sl = float(arguments.get("sl", 0.0))
        new_tp = float(arguments.get("tp", 0.0))

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return text(f"❌ No open position with ticket {ticket}.")

        pos       = positions[0]
        direction = "buy" if pos.type == mt5.ORDER_TYPE_BUY else "sell"
        tick      = mt5.symbol_info_tick(pos.symbol)
        price     = tick.ask if direction == "buy" else tick.bid

        result = mt5.order_send({
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       volume,
            "type":         pos.type,
            "price":        price,
            "sl":           new_sl,
            "tp":           new_tp,
            "deviation":    20,
            "magic":        MAGIC,
            "comment":      f"Claude Code scale in #{ticket}",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": get_filling(pos.symbol),
        })
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return text(json.dumps({
                "status":    "✅ Scaled in",
                "new_ticket": result.order,
                "symbol":    pos.symbol,
                "direction": direction.upper(),
                "added_volume": volume,
                "price":     result.price,
            }, indent=2))
        else:
            code = result.retcode if result else "None"
            msg  = result.comment if result else err()
            return text(f"❌ Scale in failed — retcode {code}: {msg}")

    # ── daily_pnl ─────────────────────────────────────────────────────────────
    elif name == "daily_pnl":
        now       = datetime.datetime.now()
        today     = now.replace(hour=0, minute=0, second=0, microsecond=0)
        deals     = mt5.history_deals_get(today, now)
        realised  = 0.0
        if deals:
            realised = round(sum(d.profit for d in deals if d.symbol), 2)

        positions  = mt5.positions_get()
        unrealised = round(sum(p.profit for p in positions), 2) if positions else 0.0

        account = mt5.account_info()
        balance = account.balance if account else None

        return text(json.dumps({
            "date":            today.strftime("%Y-%m-%d"),
            "realised_pnl":    realised,
            "unrealised_pnl":  unrealised,
            "total_pnl":       round(realised + unrealised, 2),
            "account_balance": balance,
        }, indent=2))

    # ── account_stats ─────────────────────────────────────────────────────────
    elif name == "account_stats":
        days  = int(arguments.get("days", 30))
        now   = datetime.datetime.now()
        start = now - datetime.timedelta(days=days)
        deals = mt5.history_deals_get(start, now)

        if not deals:
            return text(f"No closed trades in the last {days} days.")

        profits = [d.profit for d in deals if d.symbol and d.entry == mt5.DEAL_ENTRY_OUT and d.profit != 0]
        if not profits:
            return text("No completed trades with P&L found in this period.")

        wins   = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]

        win_rate      = round(len(wins) / len(profits) * 100, 1) if profits else 0
        avg_win       = round(sum(wins)   / len(wins),   2) if wins   else 0
        avg_loss      = round(sum(losses) / len(losses), 2) if losses else 0
        gross_profit  = round(sum(wins),   2)
        gross_loss    = round(abs(sum(losses)), 2)
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss else float("inf")

        return text(json.dumps({
            "period_days":    days,
            "total_trades":   len(profits),
            "wins":           len(wins),
            "losses":         len(losses),
            "win_rate":       f"{win_rate}%",
            "profit_factor":  profit_factor,
            "avg_win":        avg_win,
            "avg_loss":       avg_loss,
            "best_trade":     round(max(profits), 2),
            "worst_trade":    round(min(profits), 2),
            "gross_profit":   gross_profit,
            "gross_loss":     gross_loss,
            "net_pnl":        round(gross_profit - gross_loss, 2),
        }, indent=2))

    # ── risk_check ────────────────────────────────────────────────────────────
    elif name == "risk_check":
        symbol       = arguments["symbol"].upper()
        sl_pips      = float(arguments["sl_pips"])
        risk_percent = float(arguments["risk_percent"])

        account = mt5.account_info()
        if not account:
            return text(f"❌ Cannot get account info. {err()}")

        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
        if not info:
            return text(f"❌ Symbol {symbol} not found. {err()}")

        risk_amount    = account.balance * (risk_percent / 100)
        pip            = info.point * 10
        pip_value      = info.trade_contract_size * pip
        sl_value_1lot  = sl_pips * pip_value
        recommended    = round(risk_amount / sl_value_1lot, 2) if sl_value_1lot else 0

        recommended = max(info.volume_min, min(info.volume_max, recommended))
        step        = info.volume_step
        recommended = round(round(recommended / step) * step, 2)

        return text(json.dumps({
            "symbol":            symbol,
            "account_balance":   round(account.balance, 2),
            "risk_percent":      risk_percent,
            "risk_amount":       round(risk_amount, 2),
            "sl_pips":           sl_pips,
            "pip_value_per_lot": round(pip_value, 4),
            "recommended_lots":  recommended,
            "actual_risk":       round(recommended * sl_value_1lot, 2),
        }, indent=2))

    # ── cancel_all_pending ────────────────────────────────────────────────────
    elif name == "cancel_all_pending":
        symbol_filter = arguments.get("symbol", "").upper() or None
        orders = (mt5.orders_get(symbol=symbol_filter)
                  if symbol_filter else mt5.orders_get())
        if not orders:
            return text("No pending orders to cancel.")

        lines = []
        for o in orders:
            result = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
            ok = result and result.retcode == mt5.TRADE_RETCODE_DONE
            lines.append(f"{'✅' if ok else '❌'} Ticket {o.ticket} {o.symbol} {'cancelled' if ok else 'failed'}")
        return text("\n".join(lines))

    # ── close_all_in_profit ───────────────────────────────────────────────────
    elif name == "close_all_in_profit":
        symbol_filter = arguments.get("symbol", "").upper() or None
        positions     = (mt5.positions_get(symbol=symbol_filter)
                         if symbol_filter else mt5.positions_get())
        if not positions:
            return text("No open positions.")

        profitable = [p for p in positions if p.profit > 0]
        if not profitable:
            return text("No positions currently in profit.")

        lines = []
        for pos in profitable:
            ok, code = close_pos(pos)
            lines.append(f"{'✅' if ok else '❌'} Ticket {pos.ticket} {pos.symbol} +{round(pos.profit,2)} {'closed' if ok else 'failed: ' + code}")
        return text("\n".join(lines))

    # ── close_all_in_loss ─────────────────────────────────────────────────────
    elif name == "close_all_in_loss":
        symbol_filter = arguments.get("symbol", "").upper() or None
        positions     = (mt5.positions_get(symbol=symbol_filter)
                         if symbol_filter else mt5.positions_get())
        if not positions:
            return text("No open positions.")

        losing = [p for p in positions if p.profit < 0]
        if not losing:
            return text("No positions currently at a loss.")

        lines = []
        for pos in losing:
            ok, code = close_pos(pos)
            lines.append(f"{'✅' if ok else '❌'} Ticket {pos.ticket} {pos.symbol} {round(pos.profit,2)} {'closed' if ok else 'failed: ' + code}")
        return text("\n".join(lines))

    else:
        return text(f"❌ Unknown tool: {name}")


# ── Start ─────────────────────────────────────────────────────────────────────

async def main():
    log.info("MT5 MCP Server (OLD/recovery) ready — timestamps are UTC+5, not true UTC")
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
