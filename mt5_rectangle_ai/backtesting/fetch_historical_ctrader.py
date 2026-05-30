"""Fetch and cache historical candle data from cTrader Open API.

Writes the same CSV format as fetch_historical.py so LocalDataEngine
and mechanical_backtest.py work unchanged.

Usage:
    python backtesting/fetch_historical_ctrader.py --symbols EURUSD GBPUSD XAUUSD NAS100 --days 90

Output:
    data/historical/<SYMBOL>/<TF>.csv   (H4, M15, M1)
    data/historical/<SYMBOL>/symbol_info.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import queue
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAApplicationAuthReq,
    ProtoOAAccountAuthReq,
    ProtoOASymbolsListReq,
    ProtoOASymbolByIdReq,
    ProtoOAGetTrendbarsReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from twisted.internet import reactor

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "historical"

CANDLE_FIELDS = ["symbol", "timeframe", "time", "open", "high", "low", "close", "tick_volume", "spread"]

_APP_AUTH_RES     = 2101
_ACCOUNT_AUTH_RES = 2103
_SYMBOLS_LIST_RES = 2115
_SYMBOL_BY_ID_RES = 2117
_TRENDBARS_RES    = 2138
_MAX_BARS         = 4999

_TF_MAP = {
    "H4":  ProtoOATrendbarPeriod.Value("H4"),
    "M15": ProtoOATrendbarPeriod.Value("M15"),
    "M1":  ProtoOATrendbarPeriod.Value("M1"),
}

_response_queue: queue.Queue = queue.Queue()
_client: Client | None = None


def _on_message_received(client, message):
    _response_queue.put(message)


def _on_disconnected(client, reason=None):
    print(f"\nDisconnected from cTrader: {reason}", file=sys.stderr)
    sys.exit(1)


def _wait_for(payload_type: int, timeout: float = 20.0):
    """Block until a message of the expected type arrives, discard others."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        try:
            msg = _response_queue.get(timeout=min(remaining, 2.0))
            extracted = Protobuf.extract(msg)
            if extracted.payloadType == payload_type:
                return extracted
            # Different type — keep waiting
        except queue.Empty:
            continue


def _send(req):
    reactor.callFromThread(_client.send, req)


# ─────────────────────────────────────────────────────────────────────────────

def connect_and_auth() -> int:
    """Start Twisted reactor, connect, authenticate. Returns account_id."""
    global _client

    host = EndPoints.PROTOBUF_DEMO_HOST
    port = EndPoints.PROTOBUF_PORT

    _client = Client(host, port, TcpProtocol)
    _client.setMessageReceivedCallback(_on_message_received)
    _client.setDisconnectedCallback(_on_disconnected)

    def _run():
        reactor.callLater(0, _client.startService)
        reactor.run(installSignalHandlers=False)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    print(f"Connecting to {host}:{port} ...", flush=True)
    time.sleep(3)  # wait for TCP handshake

    # App auth
    req = ProtoOAApplicationAuthReq()
    req.clientId     = os.environ["CTRADER_CLIENT_ID"]
    req.clientSecret = os.environ["CTRADER_CLIENT_SECRET"]
    _send(req)
    res = _wait_for(_APP_AUTH_RES, timeout=15)
    if res is None:
        raise RuntimeError("App auth timed out — check credentials and network")
    print("App auth OK", flush=True)

    # Account auth
    account_id = int(os.environ["CTRADER_ACCOUNT_ID"])
    req = ProtoOAAccountAuthReq()
    req.ctidTraderAccountId = account_id
    req.accessToken         = os.environ["CTRADER_ACCESS_TOKEN"]
    _send(req)
    res = _wait_for(_ACCOUNT_AUTH_RES, timeout=15)
    if res is None:
        raise RuntimeError("Account auth timed out — access token may be expired")
    print(f"Account auth OK (account_id={account_id})", flush=True)

    return account_id


def get_symbol_meta(account_id: int, symbol_name: str) -> dict:
    """Return symbol_id, digits, pip_position, point."""
    req = ProtoOASymbolsListReq()
    req.ctidTraderAccountId = account_id
    _send(req)
    res = _wait_for(_SYMBOLS_LIST_RES, timeout=20)
    if res is None:
        raise RuntimeError("SymbolsListReq timed out")

    entry = next((s for s in res.symbol if s.symbolName == symbol_name), None)
    if entry is None:
        raise ValueError(f"Symbol {symbol_name!r} not found on this account")

    req2 = ProtoOASymbolByIdReq()
    req2.ctidTraderAccountId = account_id
    req2.symbolId.append(entry.symbolId)
    _send(req2)
    res2 = _wait_for(_SYMBOL_BY_ID_RES, timeout=20)
    if res2 is None:
        raise RuntimeError("SymbolByIdReq timed out")

    sym = res2.symbol[0]
    return {
        "name":         symbol_name,
        "symbol_id":    entry.symbolId,
        "digits":       sym.digits,
        "pip_position": sym.pipPosition,
        "point":        10 ** -sym.digits,
    }


def fetch_bars(account_id: int, meta: dict, tf_name: str, days: int) -> list[dict]:
    """Fetch `days` worth of bars using time-window pagination. Returns list sorted oldest-first."""
    symbol_id = meta["symbol_id"]
    # cTrader trendbars always encode prices at 1/100000 precision regardless of symbol digits
    divisor   = 100_000
    period    = _TF_MAP[tf_name]

    now_ms     = int(time.time() * 1000)
    start_ms   = now_ms - days * 24 * 3600 * 1000
    to_ts_ms   = now_ms
    all_rows: list[dict] = []

    while to_ts_ms > start_ms:
        from_ts_ms = max(start_ms, to_ts_ms - _MAX_BARS * _tf_duration_ms(tf_name))

        req = ProtoOAGetTrendbarsReq()
        req.ctidTraderAccountId = account_id
        req.symbolId            = symbol_id
        req.period              = period
        req.fromTimestamp       = from_ts_ms
        req.toTimestamp         = to_ts_ms
        req.count               = _MAX_BARS

        _send(req)
        res = _wait_for(_TRENDBARS_RES, timeout=30)
        if res is None:
            print(f"    Trendbar req timed out — stopping at {len(all_rows)}", flush=True)
            break

        bars = list(res.trendbar)
        if not bars:
            break

        chunk: list[dict] = []
        for bar in bars:
            ts_s = bar.utcTimestampInMinutes * 60
            dt   = datetime.fromtimestamp(ts_s, tz=timezone.utc).replace(tzinfo=None)
            chunk.append({
                "time":        dt.isoformat(timespec="seconds"),
                "open":        (bar.low + bar.deltaOpen)  / divisor,
                "high":        (bar.low + bar.deltaHigh)  / divisor,
                "low":          bar.low                   / divisor,
                "close":       (bar.low + bar.deltaClose) / divisor,
                "tick_volume":  bar.volume,
            })

        all_rows.extend(chunk)
        oldest_min = min(bar.utcTimestampInMinutes for bar in bars)
        to_ts_ms   = oldest_min * 60 * 1000 - 1  # step back before oldest bar
        print(f"    {tf_name}: +{len(chunk)} bars (total {len(all_rows)}, oldest {chunk[-1]['time']})", flush=True)

        if len(bars) < 10:
            break  # broker ran out of history

    # Sort ascending, deduplicate
    all_rows.sort(key=lambda r: r["time"])
    seen: set[str] = set()
    unique = [r for r in all_rows if r["time"] not in seen and not seen.add(r["time"])]  # type: ignore[func-returns-value]
    return unique


def _tf_duration_ms(tf_name: str) -> int:
    """Duration of one bar in milliseconds."""
    return {"M1": 60_000, "M15": 900_000, "H4": 14_400_000, "D1": 86_400_000}.get(tf_name, 900_000)


def save_symbol(symbol: str, days: int, data_dir: Path, account_id: int) -> None:
    print(f"\n[{symbol}] Getting symbol metadata...", flush=True)
    meta = get_symbol_meta(account_id, symbol)
    print(f"[{symbol}] symbol_id={meta['symbol_id']} digits={meta['digits']}", flush=True)

    sym_dir = data_dir / symbol
    sym_dir.mkdir(parents=True, exist_ok=True)
    (sym_dir / "symbol_info.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    specs = ["H4", "M15", "M1"]

    for tf_name in specs:
        t0 = time.monotonic()
        print(f"[{symbol}] Fetching {days}d of {tf_name} bars...", flush=True)
        bars = fetch_bars(account_id, meta, tf_name, days)

        path = sym_dir / f"{tf_name}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CANDLE_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for r in bars:
                writer.writerow({**r, "symbol": symbol, "timeframe": tf_name, "spread": 0})

        elapsed = time.monotonic() - t0
        first = bars[0]["time"] if bars else "n/a"
        last  = bars[-1]["time"] if bars else "n/a"
        print(f"[{symbol}] {len(bars):,} {tf_name} bars in {elapsed:.1f}s ({first} → {last}) -> {path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD", "XAUUSD", "NAS100"])
    parser.add_argument("--days",    type=int, default=90)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    print(f"Output: {data_dir}  |  Symbols: {args.symbols}  |  Days: {args.days}\n")

    account_id = connect_and_auth()

    for symbol in args.symbols:
        try:
            save_symbol(symbol.upper(), args.days, data_dir, account_id)
        except Exception as exc:
            print(f"[{symbol}] FAILED: {exc}", file=sys.stderr)

    print("\nAll done.")
    os._exit(0)


if __name__ == "__main__":
    main()
