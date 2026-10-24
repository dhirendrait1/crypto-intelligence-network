"""Read-only public OHLC candles with Binance and Kraken public-provider fallback."""
from __future__ import annotations

import asyncio
import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

try:
    from app.cin_technical_analysis import analyze_ohlc
except ModuleNotFoundError as exc:
    # Do not mask missing dependencies imported by the analysis module itself.
    if exc.name not in {"app", "app.cin_technical_analysis"}:
        raise
    from cin_technical_analysis import analyze_ohlc

router = APIRouter(tags=["public-market-candles"])
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"
MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024
# Largest millisecond Unix timestamp representable by Python datetime (year 9999).
MAX_TIMESTAMP_MS = 253402300799999
TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"}
KRAKEN_INTERVALS = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}
KRAKEN_SYMBOLS = {"BTC": "XBT"}


def _request_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={"accept": "application/json", "user-agent": "CIN-Research-API/0.2.0"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"Provider returned HTTP {response.status}")
        body = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        if len(body) > MAX_PROVIDER_RESPONSE_BYTES:
            raise ValueError("Provider response exceeded the configured size limit")
        return json.loads(body.decode("utf-8"))


def _is_valid_candle(candle: dict[str, Any]) -> bool:
    """Reject non-finite values, impossible OHLC ranges, and invalid timestamps."""
    try:
        prices = [float(candle[key]) for key in ("open", "high", "low", "close")]
        volume = float(candle["volume"])
        open_time = int(candle["open_time"])
        close_time = int(candle["close_time"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    open_price, high, low, close = prices
    return (
        all(math.isfinite(value) and value > 0 for value in prices)
        and math.isfinite(volume) and volume >= 0
        and high >= max(open_price, close)
        and low <= min(open_price, close)
        and high >= low
        and 0 <= open_time <= MAX_TIMESTAMP_MS
        and open_time <= close_time <= MAX_TIMESTAMP_MS
    )


def _fetch_binance(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"symbol": symbol, "interval": interval, "limit": limit})
    payload = _request_json(f"{BINANCE_KLINES_URL}?{query}")
    if not isinstance(payload, list):
        raise ValueError("Binance response was not a list")
    if len(payload) > limit:
        raise ValueError("Binance returned more candles than requested")
    candles = []
    for row in payload:
        if not isinstance(row, list) or len(row) < 7:
            continue
        try:
            # Binance timestamps are integer milliseconds. Do not silently truncate
            # fractional values or accept booleans as numeric timestamps.
            if isinstance(row[0], bool) or isinstance(row[6], bool):
                continue
            open_time_value, close_time_value = float(row[0]), float(row[6])
            if not open_time_value.is_integer() or not close_time_value.is_integer():
                continue
            candle = {
                "open_time": int(open_time_value), "open": float(row[1]), "high": float(row[2]),
                "low": float(row[3]), "close": float(row[4]), "volume": float(row[5]),
                "close_time": int(close_time_value),
            }
            if _is_valid_candle(candle):
                candles.append(candle)
        except (TypeError, ValueError, OverflowError):
            continue
    if not candles:
        raise ValueError("Binance returned no valid candles")
    return candles


def _fetch_kraken(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    if interval not in KRAKEN_INTERVALS:
        raise ValueError(f"Kraken fallback does not support interval {interval}")
    pair = re.fullmatch(r"([A-Z0-9]+)(USDT|USD)", symbol)
    if not pair:
        raise ValueError(f"Kraken fallback cannot map symbol {symbol}")
    base, quote = pair.groups()
    base = KRAKEN_SYMBOLS.get(base, base)
    # Kraken's public OHLC supports USD and USDT pairs; retain the requested quote.
    kraken_pair = f"{base}{quote}"
    query = urllib.parse.urlencode({"pair": kraken_pair, "interval": KRAKEN_INTERVALS[interval]})
    payload = _request_json(f"{KRAKEN_OHLC_URL}?{query}")
    if not isinstance(payload, dict):
        raise ValueError("Kraken response was not an object")
    errors = payload.get("error") or []
    if errors:
        raise ValueError("Kraken rejected pair/timeframe: " + "; ".join(str(e) for e in errors))
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("Kraken response had no result")
    pair_key = next((key for key in result if key != "last"), None)
    rows = result.get(pair_key) if pair_key else None
    if not isinstance(rows, list):
        raise ValueError("Kraken returned no candle rows")
    candles = []
    # Validate rows before applying the requested limit so malformed tail rows
    # do not unnecessarily reduce the number of usable recent candles.
    for row in rows:
        if not isinstance(row, list) or len(row) < 7:
            continue
        try:
            start = int(float(row[0]) * 1000)
            # Kraken returns OHLC, VWAP, volume, trade count; derive candle end
            # from the selected timeframe so the output schema matches Binance.
            duration_ms = KRAKEN_INTERVALS[interval] * 60_000
            candle = {
                "open_time": start, "open": float(row[1]), "high": float(row[2]),
                "low": float(row[3]), "close": float(row[4]), "volume": float(row[6]),
                "close_time": start + duration_ms - 1,
            }
            if _is_valid_candle(candle):
                candles.append(candle)
        except (TypeError, ValueError, OverflowError):
            continue
    if not candles:
        raise ValueError("Kraken returned no valid candles")
    return candles[-limit:]


def _normalize_candle_sequence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return candles in chronological order and reject ambiguous duplicate timestamps."""
    ordered = sorted(rows, key=lambda row: row["open_time"])
    for previous, current in zip(ordered, ordered[1:]):
        if current["open_time"] == previous["open_time"]:
            raise ValueError("Provider returned duplicate candle open timestamps")
    return ordered


def _fetch_klines(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    """Compatibility wrapper retained for existing tests and integrations."""
    return _fetch_binance(symbol, interval, limit)


async def _load(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    try:
        rows = await asyncio.to_thread(_fetch_binance, symbol, interval, limit)
        source, endpoint = "Binance public market-data API", BINANCE_KLINES_URL
    except urllib.error.HTTPError as exc:
        if exc.code != 451:
            if exc.code in (418, 429):
                raise HTTPException(status_code=503, detail="Public market-data rate limit reached; retry later.") from exc
            raise HTTPException(status_code=502, detail=f"Binance public market-data provider returned HTTP {exc.code}.") from exc
        try:
            rows = await asyncio.to_thread(_fetch_kraken, symbol, interval, limit)
            source, endpoint = "Kraken public OHLC API (fallback after Binance HTTP 451)", KRAKEN_OHLC_URL
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as fallback_exc:
            # Do not disguise fallback failure or return stale/empty data as live.
            reason = "Kraken fallback unavailable or pair/timeframe unsupported"
            if isinstance(fallback_exc, urllib.error.HTTPError):
                reason += f" (HTTP {fallback_exc.code})"
            raise HTTPException(status_code=503, detail=reason + "; Binance returned HTTP 451.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise HTTPException(status_code=503, detail="Binance public market-data provider is temporarily unavailable.") from None
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="Binance public market-data provider returned an invalid response.") from None
    try:
        rows = _normalize_candle_sequence(rows)
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="Public market-data provider returned an ambiguous candle sequence.") from None
    for row in rows:
        row["_source"] = source
        row["_source_endpoint"] = endpoint
    return rows


def _validate(symbol: str, interval: str, limit: int) -> str:
    normalized = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{5,20}", normalized):
        raise HTTPException(status_code=400, detail="Symbol must be a trading pair such as BTCUSDT.")
    if interval not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Unsupported interval.")
    if not 5 <= limit <= 500:
        raise HTTPException(status_code=400, detail="Limit must be between 5 and 500.")
    return normalized


@router.get("/market-candles")
async def get_market_candles(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20),
    interval: str = Query(default="1h"),
    limit: int = Query(default=100, ge=5, le=500),
) -> dict[str, Any]:
    """Retrieve timestamped public OHLCV candles with source provenance."""
    normalized = _validate(symbol, interval, limit)
    rows = await _load(normalized, interval, limit)
    source = rows[0].get("_source", "Binance public market-data API")
    endpoint = rows[0].get("_source_endpoint", BINANCE_KLINES_URL)
    return {
        "service": "cin", "mode": "read_only", "source": source, "source_endpoint": endpoint,
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "symbol": normalized,
        "timeframe": interval, "count": len(rows),
        "data": [
            {
                **{key: value for key, value in row.items() if not key.startswith("_")},
                "open_time_utc": datetime.fromtimestamp(row["open_time"] / 1000, timezone.utc).isoformat(),
                "close_time_utc": datetime.fromtimestamp(row["close_time"] / 1000, timezone.utc).isoformat(),
            }
            for row in rows
        ],
        "limitations": [
            "Public exchange-provided market data; not independently audited by CIN.",
            "The latest candle may still be forming.",
            "The source exchange can differ when a provider fallback is used.",
            "No account endpoints, API keys, orders, or trade execution are used.",
        ],
    }


@router.get("/technical-analysis/market")
async def analyze_public_market(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20),
    interval: str = Query(default="1h"),
    limit: int = Query(default=100, ge=5, le=500),
) -> dict[str, Any]:
    """Fetch public OHLCV and run CIN's existing deterministic technical analysis."""
    normalized = _validate(symbol, interval, limit)
    rows = await _load(normalized, interval, limit)
    source = rows[0].get("_source", "Binance public market-data API")
    endpoint = rows[0].get("_source_endpoint", BINANCE_KLINES_URL)
    try:
        analysis = analyze_ohlc([{key: row[key] for key in ("open", "high", "low", "close")} for row in rows])
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Fetched candles failed analysis validation: {exc}") from exc
    analysis["input"].update({
        "symbol": normalized, "timeframe": interval, "source": source, "source_endpoint": endpoint,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "first_candle_open_time_utc": datetime.fromtimestamp(rows[0]["open_time"] / 1000, timezone.utc).isoformat(),
        "last_candle_close_time_utc": datetime.fromtimestamp(rows[-1]["close_time"] / 1000, timezone.utc).isoformat(),
        "volume_included_in_source_but_not_used_in_indicators": True,
    })
    analysis["limitations"].extend([
        "Public exchange data is not independently audited by CIN.",
        "The last candle may still be forming; confirm closed-candle status before comparing snapshots.",
        "Technical outputs and ATR scenarios are descriptive research, not investment advice or trade instructions.",
    ])
    return analysis
