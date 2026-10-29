"""Read-only public OHLC candles with quote-safe, Coinbase-first provider selection."""
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

from cin_market_candle_provenance import candle_observation_metadata, market_pair_metadata

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
_INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
    "12h": 43_200_000, "1d": 86_400_000, "3d": 259_200_000,
    "1w": 604_800_000, "1M": 2_678_400_000,
}


def _interval_duration_ms(interval: str, open_time_ms: int | None = None) -> int:
    """Return interval duration; monthly candles use calendar-month boundaries."""
    if interval != "1M" or open_time_ms is None:
        return _INTERVAL_MS[interval]
    start = datetime.fromtimestamp(open_time_ms / 1000, timezone.utc)
    if start.month == 12:
        next_month = datetime(start.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(start.year, start.month + 1, 1, tzinfo=timezone.utc)
    return int(next_month.timestamp() * 1000) - open_time_ms


def _freshness_metadata(rows: list[dict[str, Any]], interval: str, now_ms: int) -> dict[str, Any]:
    """Report completed-candle freshness without implying provider verification."""
    closed_rows = [row for row in rows if row["close_time"] < now_ms]
    latest = max(closed_rows, key=lambda row: row["close_time"]) if closed_rows else None
    duration_ms = _interval_duration_ms(interval, latest["open_time"] if latest else None)
    threshold_seconds = duration_ms * 2 / 1000
    if not closed_rows:
        return {
            "latest_closed_candle_close_time_utc": None,
            "latest_closed_candle_age_seconds": None,
            "stale_data_warning": "No completed candle is available; do not treat a forming candle as closed data.",
            "stale_threshold_seconds": threshold_seconds,
        }
    age_seconds = max(0.0, (now_ms - latest["close_time"]) / 1000)
    warning = f"Latest completed candle is older than the interval {interval} freshness threshold." if age_seconds > threshold_seconds else None
    return {
        "latest_closed_candle_close_time_utc": datetime.fromtimestamp(latest["close_time"] / 1000, timezone.utc).isoformat(),
        "latest_closed_candle_age_seconds": round(age_seconds, 3),
        "stale_data_warning": warning,
        "stale_threshold_seconds": threshold_seconds,
    }




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
    errors = payload.get("error")
    # Kraken's response envelope must contain a well-formed error list.
    if not isinstance(errors, list) or any(not isinstance(error, str) or not error.strip() for error in errors):
        raise ValueError("Kraken response error field was malformed")
    if errors:
        raise ValueError("Kraken rejected pair/timeframe: " + "; ".join(errors))
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("Kraken response had no result")
    # The response key is the only provider-returned market identity. Accept
    # explicit aliases for this exact base/quote; never take an arbitrary key.
    result_keys = [key for key in result if key != "last"]
    base_alias = "XBT" if base == "XBT" else base
    quote_alias = "ZUSD" if quote == "USD" else quote
    accepted_pair_keys = {
        f"{base_alias}{quote}",
        f"X{base_alias}{quote_alias}",
    }
    if base_alias == "XBT":
        accepted_pair_keys.add(f"XXBT{quote_alias}")
    matching_keys = [key for key in result_keys if key in accepted_pair_keys]
    if len(matching_keys) != 1:
        if not matching_keys:
            raise ValueError("Kraken response market key did not match requested pair")
        raise ValueError("Kraken response contained ambiguous market keys for requested pair")
    pair_key = matching_keys[0]
    rows = result.get(pair_key)
    if not isinstance(rows, list):
        raise ValueError("Kraken returned no candle rows")
    candles = []
    # Validate rows before applying the requested limit so malformed tail rows
    # do not unnecessarily reduce the number of usable recent candles.
    for row in rows:
        if not isinstance(row, list) or len(row) < 7:
            continue
        try:
            # Kraken timestamps are seconds. Reject booleans, non-finite values,
            # and fractional seconds rather than silently truncating source data.
            if isinstance(row[0], bool):
                continue
            start_seconds = float(row[0])
            if not math.isfinite(start_seconds) or not start_seconds.is_integer():
                continue
            start = int(start_seconds * 1000)
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



COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
COINBASE_GRANULARITY = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}


def _fetch_coinbase(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    """Fetch public Coinbase Exchange candles when primary providers are blocked."""
    if interval not in COINBASE_GRANULARITY:
        raise ValueError(f"Coinbase fallback does not support interval {interval}")
    pair = re.fullmatch(r"([A-Z0-9]+)(USDT|USD)", symbol)
    if not pair:
        raise ValueError(f"Coinbase fallback cannot map symbol {symbol}")
    base, quote = pair.groups()
    # Never substitute a USD market for a USDT request: the quote asset is part
    # of the market identity and must not be silently changed.
    if quote != "USD":
        raise ValueError("Coinbase fallback requires an exact USD-quoted symbol")
    product_id = f"{base}-USD"
    duration = COINBASE_GRANULARITY[interval]
    now = int(datetime.now(timezone.utc).timestamp())
    start = now - limit * duration
    rows_by_time: dict[int, list[Any]] = {}
    # Coinbase caps each response at 300 candles; fetch bounded adjacent windows.
    cursor = start
    while cursor < now:
        chunk_end = min(now, cursor + 300 * duration)
        query = urllib.parse.urlencode({
            "granularity": duration,
            "start": datetime.fromtimestamp(cursor, timezone.utc).isoformat(),
            "end": datetime.fromtimestamp(chunk_end, timezone.utc).isoformat(),
        })
        url = COINBASE_CANDLES_URL.format(product_id=urllib.parse.quote(product_id, safe="")) + "?" + query
        payload = _request_json(url)
        if not isinstance(payload, list):
            raise ValueError("Coinbase response was not a list")
        for row in payload:
            if not isinstance(row, list) or len(row) < 6:
                continue
            try:
                # Coinbase timestamps are integer Unix seconds. Reject booleans,
                # fractional values, non-finite numbers, and out-of-range times.
                if isinstance(row[0], bool):
                    continue
                timestamp_seconds = float(row[0])
                if (not math.isfinite(timestamp_seconds)
                        or not timestamp_seconds.is_integer()
                        or timestamp_seconds < 0
                        or timestamp_seconds * 1000 > MAX_TIMESTAMP_MS):
                    continue
                rows_by_time[int(timestamp_seconds)] = row
            except (TypeError, ValueError, OverflowError):
                continue
        cursor = chunk_end
    candles = []
    for row in sorted(rows_by_time.values(), key=lambda item: int(item[0]))[-limit:]:
        try:
            start_ms = int(row[0]) * 1000
            duration_ms = duration * 1000
            # Coinbase rows are [time, low, high, open, close, volume].
            candle = {
                "open_time": start_ms, "open": float(row[3]), "high": float(row[2]),
                "low": float(row[1]), "close": float(row[4]), "volume": float(row[5]),
                "close_time": start_ms + duration_ms - 1,
            }
            if _is_valid_candle(candle):
                candles.append(candle)
        except (TypeError, ValueError, OverflowError):
            continue
    if not candles:
        raise ValueError("Coinbase returned no valid candles")
    return candles


def _fetch_klines(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    """Compatibility wrapper retained for existing tests and integrations."""
    return _fetch_binance(symbol, interval, limit)


async def _load(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    """Load public candles with Coinbase first where its quote matches exactly.

    USD requests prefer Coinbase Exchange. USDT requests prefer Kraken because
    Coinbase's spot candle endpoint here is USD-quoted only. Binance is the
    final public fallback; no fallback is allowed to relabel a USD market as USDT.
    """
    match = re.fullmatch(r"([A-Z0-9]+)(USDT|USD)", symbol)
    if not match:
        raise HTTPException(status_code=400, detail="Symbol must be a supported USD or USDT trading pair.")
    _, quote = match.groups()
    if quote == "USD":
        providers = [
            (_fetch_coinbase, "Coinbase Exchange public candles API", COINBASE_CANDLES_URL),
            (_fetch_kraken, "Kraken public OHLC API (fallback)", KRAKEN_OHLC_URL),
            (_fetch_binance, "Binance public market-data API (fallback)", BINANCE_KLINES_URL),
        ]
    else:
        providers = [
            (_fetch_kraken, "Kraken public OHLC API", KRAKEN_OHLC_URL),
            (_fetch_binance, "Binance public market-data API (fallback)", BINANCE_KLINES_URL),
        ]

    failures: list[tuple[str, Exception]] = []
    rows = None
    source = endpoint = None
    for fetcher, provider_name, provider_endpoint in providers:
        try:
            rows = await asyncio.to_thread(fetcher, symbol, interval, limit)
            source, endpoint = provider_name, provider_endpoint
            break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
            failures.append((provider_name, exc))

    if rows is None:
        # Rate-limit responses should be retried later, not mistaken for valid data.
        if any(isinstance(exc, urllib.error.HTTPError) and exc.code in (418, 429) for _, exc in failures):
            raise HTTPException(status_code=503, detail="Public market-data rate limit reached; retry later.") from None
        raise HTTPException(status_code=503, detail="No quote-compatible public market-data provider returned valid candles.") from None

    try:
        rows = _normalize_candle_sequence(rows)
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="Public market-data provider returned an ambiguous candle sequence.") from None
    for row in rows:
        row["_source"] = source
        row["_source_endpoint"] = endpoint
        row["_requested_quote_currency"] = quote
        row["_actual_quote_currency"] = quote
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
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    freshness = _freshness_metadata(rows, interval, now_ms)
    source = rows[0].get("_source", "Binance public market-data API")
    endpoint = rows[0].get("_source_endpoint", BINANCE_KLINES_URL)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    source_id = ("coinbase_public" if source.startswith("Coinbase") else
                 "kraken_public" if source.startswith("Kraken") else "binance_public")
    pair_metadata = market_pair_metadata(normalized, source_id)
    requested_quote = pair_metadata["requested_quote_currency"]
    actual_quote = pair_metadata["quote_currency"]
    return {
        "service": "cin", "mode": "read_only", "source": source, "source_id": source_id,
        "source_endpoint": endpoint, "retrieved_at": retrieved_at, "symbol": normalized,
        **pair_metadata, "actual_quote_currency": actual_quote,
        "timeframe": interval, "count": len(rows),
        **freshness,
        "data": [
            {
                **{key: value for key, value in row.items() if not key.startswith("_")},
                "open_time_utc": datetime.fromtimestamp(row["open_time"] / 1000, timezone.utc).isoformat(),
                "close_time_utc": datetime.fromtimestamp(row["close_time"] / 1000, timezone.utc).isoformat(),
                "is_closed": row["close_time"] < now_ms,
                "observation_metadata": candle_observation_metadata(
                    source_id=source_id,
                    observed_at=datetime.fromtimestamp(
                        (row["close_time"] if row["close_time"] < now_ms else row["open_time"]) / 1000,
                        timezone.utc,
                    ).isoformat(),
                    retrieved_at=retrieved_at,
                    interval=interval,
                    quote_currency=actual_quote,
                    timestamp_semantics=("candle_close_time" if row["close_time"] < now_ms else "candle_open_time"),
                ),
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
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    closed_rows = [row for row in rows if row["close_time"] < now_ms]
    if len(closed_rows) < 5:
        raise HTTPException(status_code=422, detail="At least five completed candles are required for market technical analysis.")
    freshness = _freshness_metadata(rows, interval, now_ms)
    source = rows[0].get("_source", "Binance public market-data API")
    endpoint = rows[0].get("_source_endpoint", BINANCE_KLINES_URL)
    source_id = ("coinbase_public" if source.startswith("Coinbase") else
                 "kraken_public" if source.startswith("Kraken") else "binance_public")
    pair_metadata = market_pair_metadata(normalized, source_id)
    requested_quote = pair_metadata["requested_quote_currency"]
    actual_quote = pair_metadata["quote_currency"]
    try:
        analysis = analyze_ohlc([{key: row[key] for key in ("open", "high", "low", "close")} for row in closed_rows])
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Fetched candles failed analysis validation: {exc}") from exc
    analysis["input"].update({
        "symbol": normalized, "timeframe": interval, "source": source, "source_endpoint": endpoint,
        "source_id": source_id, **pair_metadata, "actual_quote_currency": actual_quote,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "requested_candle_count": len(rows),
        "analysis_candle_count": len(closed_rows),
        "forming_candle_excluded_count": len(rows) - len(closed_rows),
        "candle_closure_policy": "technical analysis uses only candles whose close_time is earlier than retrieval time",
        "first_candle_open_time_utc": datetime.fromtimestamp(closed_rows[0]["open_time"] / 1000, timezone.utc).isoformat(),
        "last_candle_close_time_utc": datetime.fromtimestamp(closed_rows[-1]["close_time"] / 1000, timezone.utc).isoformat(),
        "volume_included_in_source_but_not_used_in_indicators": True,
        **freshness,
    })
    analysis["limitations"].extend([
        "Public exchange data is not independently audited by CIN.",
        "The market-candles endpoint labels forming candles; the technical-analysis endpoint excludes them.",
        "Technical outputs and ATR scenarios are descriptive research, not investment advice or trade instructions.",
    ])
    return analysis
