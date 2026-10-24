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
except ModuleNotFoundError:
    from cin_technical_analysis import analyze_ohlc

router = APIRouter(tags=["public-market-candles"])
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"
TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"}
KRAKEN_INTERVALS = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}
KRAKEN_SYMBOLS = {"BTC": "XBT"}
_MAX_PROVIDER_RESPONSE_BYTES = 2_000_000
_INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
    "12h": 43_200_000, "1d": 86_400_000, "3d": 259_200_000,
    "1w": 604_800_000, "1M": 2_678_400_000,
}

def _freshness_metadata(rows: list[dict[str, Any]], interval: str, now_ms: int) -> dict[str, Any]:
    closed_rows = [row for row in rows if row["close_time"] < now_ms]
    threshold_seconds = _INTERVAL_MS[interval] * 2 / 1000
    if not closed_rows:
        return {
            "latest_closed_candle_close_time_utc": None,
            "latest_closed_candle_age_seconds": None,
            "stale_data_warning": "No completed candle is available; do not treat a forming candle as closed data.",
            "stale_threshold_seconds": threshold_seconds,
        }
    latest = max(closed_rows, key=lambda row: row["close_time"])
    age_seconds = max(0.0, (now_ms - latest["close_time"]) / 1000)
    warning = f"Latest completed candle is older than the {interval} freshness threshold." if age_seconds > threshold_seconds else None
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
        # Read at most one byte beyond the cap so oversized provider payloads
        # are rejected before unbounded buffering or JSON parsing.
        body = response.read(_MAX_PROVIDER_RESPONSE_BYTES + 1)
        if len(body) > _MAX_PROVIDER_RESPONSE_BYTES:
            raise ValueError("Public market-data provider response exceeded the configured size limit")
        return json.loads(body.decode("utf-8"))



def _valid_candle(row: dict[str, Any]) -> bool:
    """Reject malformed provider rows before exposing them or analyzing them."""
    try:
        open_time = row["open_time"]
        close_time = row["close_time"]
        prices = [row[key] for key in ("open", "high", "low", "close")]
        volume = row["volume"]
        if isinstance(open_time, bool) or not isinstance(open_time, int) or open_time < 0:
            return False
        if isinstance(close_time, bool) or not isinstance(close_time, int) or close_time < open_time:
            return False
        # Reject timestamps that cannot be represented as UTC datetimes before
        # freshness metadata or response serialization attempts to convert them.
        datetime.fromtimestamp(open_time / 1000, timezone.utc)
        datetime.fromtimestamp(close_time / 1000, timezone.utc)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in prices):
            return False
        if any(not math.isfinite(value) or value <= 0 for value in prices):
            return False
        open_price, high, low, close = prices
        if high < max(open_price, low, close) or low > min(open_price, high, close):
            return False
        if isinstance(volume, bool) or not isinstance(volume, (int, float)):
            return False
        if not math.isfinite(volume) or volume < 0:
            return False
        return True
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        return False


def _clean_candles(candles: list[dict[str, Any]], provider: str) -> list[dict[str, Any]]:
    """Keep valid, unique candles; reject conflicting evidence for one open time."""
    by_open_time: dict[int, dict[str, Any]] = {}
    comparable_fields = ("open_time", "close_time", "open", "high", "low", "close", "volume")
    for row in candles:
        if not _valid_candle(row):
            continue
        open_time = row["open_time"]
        previous = by_open_time.get(open_time)
        if previous is not None:
            if any(previous.get(field) != row.get(field) for field in comparable_fields):
                raise ValueError(f"{provider} returned conflicting candles for the same open timestamp")
            continue
        by_open_time[open_time] = row
    cleaned = [by_open_time[key] for key in sorted(by_open_time)]
    if not cleaned:
        raise ValueError(f"{provider} returned no valid candles")
    return cleaned


def _fetch_binance(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"symbol": symbol, "interval": interval, "limit": limit})
    payload = _request_json(f"{BINANCE_KLINES_URL}?{query}")
    if not isinstance(payload, list):
        raise ValueError("Binance response was not a list")
    candles = []
    for row in payload:
        if not isinstance(row, list) or len(row) < 7:
            continue
        # JSON booleans are Python integers; do not coerce them into timestamps.
        if isinstance(row[0], bool) or isinstance(row[6], bool):
            continue
        # Reject booleans in numeric OHLCV fields before float() turns True/False
        # into plausible prices or volume values.
        if any(isinstance(row[index], bool) for index in (1, 2, 3, 4, 5)):
            continue
        try:
            # Binance timestamps are integer milliseconds. Reject fractional or
            # string-coercible timestamps instead of truncating malformed data.
            if not isinstance(row[0], int) or not isinstance(row[6], int):
                continue
            candles.append({
                "open_time": row[0], "open": float(row[1]), "high": float(row[2]),
                "low": float(row[3]), "close": float(row[4]), "volume": float(row[5]),
                "close_time": row[6],
            })
        except (TypeError, ValueError, OverflowError):
            continue
    cleaned = _clean_candles(candles, "Binance")
    if len(cleaned) > limit:
        raise ValueError("Binance returned more candles than the requested limit")
    return cleaned


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
    pair_keys = [key for key in result if key != "last"]
    if len(pair_keys) != 1:
        raise ValueError("Kraken response did not identify exactly one requested trading pair")
    pair_key = pair_keys[0]
    # Kraken may return legacy asset prefixes (for example XXBTZUSD) instead
    # of the request spelling. Validate the returned identity before exposing
    # its candles; never assume the first result key matches the requested pair.
    requested_base, requested_quote = base, quote
    key_upper = pair_key.upper()
    if key_upper.endswith("ZUSD"):
        returned_quote = "USD"
        returned_base = key_upper[:-4]
    elif key_upper.endswith("USD"):
        returned_quote = "USD"
        returned_base = key_upper[:-3]
    elif key_upper.endswith("USDT"):
        returned_quote = "USDT"
        returned_base = key_upper[:-4]
    else:
        raise ValueError("Kraken returned an unsupported quote currency")
    if returned_base.startswith("X") and len(returned_base) > 3:
        returned_base = returned_base[1:]
    returned_base = {"XBT": "BTC"}.get(returned_base, returned_base)
    requested_base = {"XBT": "BTC"}.get(requested_base, requested_base)
    if returned_quote != requested_quote or returned_base != requested_base:
        raise ValueError("Kraken returned a different trading pair than requested")
    rows = result.get(pair_key)
    if not isinstance(rows, list):
        raise ValueError("Kraken returned no candle rows")
    candles = []
    for row in rows[-limit:]:
        if not isinstance(row, list) or len(row) < 7:
            continue
        # Kraken timestamps are epoch seconds; reject booleans, strings,
        # and fractional seconds instead of silently coercing/truncating them.
        if isinstance(row[0], bool) or not isinstance(row[0], (int, float)):
            continue
        if not math.isfinite(row[0]) or not float(row[0]).is_integer():
            continue
        # Kraken OHLC and volume fields must not be JSON booleans either.
        if any(isinstance(row[index], bool) for index in (1, 2, 3, 4, 6)):
            continue
        try:
            start = int(row[0] * 1000)
            # Kraken returns OHLC, VWAP, volume, trade count; derive candle end
            # from the selected timeframe so the output schema matches Binance.
            duration_ms = KRAKEN_INTERVALS[interval] * 60_000
            candles.append({
                "open_time": start, "open": float(row[1]), "high": float(row[2]),
                "low": float(row[3]), "close": float(row[4]), "volume": float(row[6]),
                "close_time": start + duration_ms - 1,
                "_provider_pair_key": pair_key,
                "_provider_quote_currency": (
                    "USD" if pair_key.upper().endswith(("ZUSD", "USD"))
                    else "USDT" if pair_key.upper().endswith("USDT")
                    else None
                ),
            })
        except (TypeError, ValueError, OverflowError):
            continue
    return _clean_candles(candles, "Kraken")


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
        except Exception as fallback_exc:
            # Do not disguise fallback failure or return stale/empty data as live.
            reason = "Kraken fallback unavailable or pair/timeframe unsupported"
            if isinstance(fallback_exc, urllib.error.HTTPError):
                reason += f" (HTTP {fallback_exc.code})"
            raise HTTPException(status_code=503, detail=reason + "; Binance returned HTTP 451.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise HTTPException(status_code=503, detail="Binance public market-data provider is temporarily unavailable.") from None
    except (ValueError, json.JSONDecodeError, RuntimeError, UnicodeDecodeError, TypeError, KeyError, OverflowError, IndexError):
        raise HTTPException(status_code=502, detail="Public market-data provider returned an invalid response.") from None
    except Exception:
        # Prevent unforeseen provider/parser failures from escaping as HTTP 500.
        raise HTTPException(status_code=502, detail="Public market-data provider returned an invalid response.") from None
    requested_pair = re.fullmatch(r"([A-Z0-9]+)(USDT|USD)", symbol)
    for row in rows:
        row["_source"] = source
        row["_source_endpoint"] = endpoint
        if source.startswith("Binance"):
            row["_provider_pair_key"] = symbol
            row["_provider_quote_currency"] = requested_pair.group(2) if requested_pair else None
    return rows


def _validate(symbol: str, interval: str, limit: int) -> str:
    if not isinstance(symbol, str) or symbol != symbol.strip() or re.fullmatch(r"[A-Za-z0-9]{5,20}", symbol) is None:
        raise HTTPException(status_code=400, detail="Symbol must be a trading pair such as BTCUSDT.")
    normalized = symbol.upper()
    if not re.fullmatch(r"[A-Z0-9]{5,20}", normalized):
        raise HTTPException(status_code=400, detail="Symbol must be a trading pair such as BTCUSDT.")
    if interval not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Unsupported interval.")
    if not 5 <= limit <= 500:
        raise HTTPException(status_code=400, detail="Limit must be between 5 and 500.")
    return normalized


@router.get(
    "/market-candles",
    responses={
        400: {"description": "Unsupported interval or semantic parameter validation failure."},
        502: {"description": "Public market-data provider or response is invalid."},
        503: {"description": "Public market-data provider is temporarily unavailable."},
    },
)
async def get_market_candles(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"),
    interval: str = Query(default="1h"),
    limit: int = Query(default=100, ge=5, le=500),
) -> dict[str, Any]:
    """Retrieve timestamped public OHLCV candles with source provenance."""
    normalized = _validate(symbol, interval, limit)
    rows = await _load(normalized, interval, limit)
    source = rows[0].get("_source", "Binance public market-data API")
    endpoint = rows[0].get("_source_endpoint", BINANCE_KLINES_URL)
    retrieved_at = datetime.now(timezone.utc)
    now_ms = int(retrieved_at.timestamp() * 1000)
    freshness = _freshness_metadata(rows, interval, now_ms)
    return {
        "service": "cin", "mode": "read_only", "source": source, "source_endpoint": endpoint,
        "retrieved_at": retrieved_at.isoformat(), "symbol": normalized,
        "provider_pair_key": rows[0].get("_provider_pair_key"),
        "provider_quote_currency": rows[0].get("_provider_quote_currency"),
        "timeframe": interval, "count": len(rows),
        "freshness": freshness,
        "data": [
            {
                **{key: value for key, value in row.items() if not key.startswith("_")},
                "open_time_utc": datetime.fromtimestamp(row["open_time"] / 1000, timezone.utc).isoformat(),
                "close_time_utc": datetime.fromtimestamp(row["close_time"] / 1000, timezone.utc).isoformat(),
                "is_closed": row["close_time"] < now_ms,
                "candle_status": "closed" if row["close_time"] < now_ms else "forming",
            }
            for row in rows
        ],
        "limitations": [
            "Public exchange-provided market data; not independently audited by CIN.",
            "The latest candle may still be forming.",
            "Freshness warning compares latest completed candle age against twice the requested interval; monthly intervals use a 31-day approximation.",
            "The source exchange can differ when a provider fallback is used.",
            "No account endpoints, API keys, orders, or trade execution are used.",
        ],
    }


@router.get(
    "/technical-analysis/market",
    responses={
        400: {"description": "Unsupported interval or semantic parameter validation failure."},
        422: {"description": "Insufficient completed candles for analysis."},
        502: {"description": "Public market-data provider or technical analysis failed."},
        503: {"description": "Public market-data provider is temporarily unavailable."},
    },
)
async def analyze_public_market(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"),
    interval: str = Query(default="1h"),
    limit: int = Query(default=100, ge=5, le=500),
) -> dict[str, Any]:
    """Fetch public OHLCV and run CIN's existing deterministic technical analysis."""
    normalized = _validate(symbol, interval, limit)
    rows = await _load(normalized, interval, limit)
    source = rows[0].get("_source", "Binance public market-data API")
    endpoint = rows[0].get("_source_endpoint", BINANCE_KLINES_URL)
    retrieved_at = datetime.now(timezone.utc)
    now_ms = int(retrieved_at.timestamp() * 1000)
    freshness = _freshness_metadata(rows, interval, now_ms)
    closed_rows = [row for row in rows if row["close_time"] < now_ms]
    forming_count = len(rows) - len(closed_rows)
    if len(closed_rows) < 5:
        raise HTTPException(
            status_code=422,
            detail="Fewer than 5 completed candles are available for analysis; retry after more candles close.",
        )
    try:
        analysis = analyze_ohlc([{key: row[key] for key in ("open", "high", "low", "close", "volume")} for row in closed_rows])
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Fetched candles failed technical-analysis validation.",
        ) from exc
    except Exception as exc:
        # Keep unexpected analysis/runtime failures within the public API contract.
        raise HTTPException(
            status_code=502,
            detail="Technical analysis failed on the fetched candle data.",
        ) from exc
    analysis["input"].update({
        "symbol": normalized, "timeframe": interval, "source": source, "source_endpoint": endpoint,
        "provider_pair_key": rows[0].get("_provider_pair_key"),
        "provider_quote_currency": rows[0].get("_provider_quote_currency"),
        "retrieved_at": retrieved_at.isoformat(),
        "freshness": freshness,
        "candles_requested": len(rows),
        "candles_used": len(closed_rows),
        "closed_candles_only": True,
        "forming_candles_excluded": forming_count,
        "first_candle_open_time_utc": datetime.fromtimestamp(closed_rows[0]["open_time"] / 1000, timezone.utc).isoformat(),
        "last_candle_close_time_utc": datetime.fromtimestamp(closed_rows[-1]["close_time"] / 1000, timezone.utc).isoformat(),
        "volume_included_in_source": all("volume" in row for row in closed_rows),
    })
    analysis["limitations"].extend([
        "Public exchange data is not independently audited by CIN.",
        "This endpoint excludes forming candles from analysis; /market-candles may still report the latest candle as forming.",
        "Freshness warning compares latest completed candle age against twice the requested interval; monthly intervals use a 31-day approximation.",
        "Technical outputs and ATR scenarios are descriptive research, not investment advice or trade instructions.",
    ])
    return analysis
