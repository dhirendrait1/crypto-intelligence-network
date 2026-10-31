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


def _timeline_integrity_metadata(rows: list[dict[str, Any]], interval: str) -> dict[str, Any]:
    """Report missing expected opens between returned candles; never fill gaps."""
    if interval not in TIMEFRAMES:
        raise ValueError("Unsupported timeline interval")
    ordered = sorted(rows, key=lambda row: row["open_time"])
    gaps = []
    missing_total = 0
    for previous, current in zip(ordered, ordered[1:]):
        expected = previous["open_time"] + _interval_duration_ms(interval, previous["open_time"])
        if current["open_time"] <= expected:
            continue
        cursor, missing = expected, 0
        while cursor < current["open_time"]:
            missing += 1
            cursor += _interval_duration_ms(interval, cursor)
        if cursor != current["open_time"]:
            raise ValueError("Candle timestamps do not align to the requested interval")
        missing_total += missing
        gaps.append({
            "after_open_time": previous["open_time"],
            "before_open_time": current["open_time"],
            "expected_next_open_time": expected,
            "missing_interval_count": missing,
        })
    return {
        "interval": interval, "has_gaps": bool(gaps), "gap_count": len(gaps),
        "missing_interval_count": missing_total, "gaps": gaps,
        "scope": "between_returned_candles_only", "missing_candles_synthesized": False,
    }


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
            "freshness_status": "no_completed_candle",
            "is_stale": None,
            "stale_data_warning": "No completed candle is available; do not treat a forming candle as closed data.",
            "stale_threshold_seconds": threshold_seconds,
        }
    age_seconds = max(0.0, (now_ms - latest["close_time"]) / 1000)
    is_stale = age_seconds > threshold_seconds
    warning = f"Latest completed candle is older than the interval {interval} freshness threshold." if is_stale else None
    return {
        "latest_closed_candle_close_time_utc": datetime.fromtimestamp(latest["close_time"] / 1000, timezone.utc).isoformat(),
        "latest_closed_candle_age_seconds": round(age_seconds, 3),
        "freshness_status": "stale" if is_stale else "fresh",
        "is_stale": is_stale,
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
        raw_open_time, raw_close_time = candle["open_time"], candle["close_time"]
        if isinstance(raw_open_time, bool) or isinstance(raw_close_time, bool):
            return False
        open_time_value, close_time_value = float(raw_open_time), float(raw_close_time)
        if not open_time_value.is_integer() or not close_time_value.is_integer():
            return False
        open_time, close_time = int(open_time_value), int(close_time_value)
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


def _is_aligned_candle_open(open_time_ms: int, interval: str) -> bool:
    """Check UTC timeframe boundaries; crypto markets have no daily session close."""
    if interval not in TIMEFRAMES or isinstance(open_time_ms, bool) or not isinstance(open_time_ms, int):
        return False
    if interval == "1M":
        value = datetime.fromtimestamp(open_time_ms / 1000, timezone.utc)
        return value.day == 1 and value.hour == value.minute == value.second == value.microsecond == 0
    duration = _INTERVAL_MS[interval]
    if interval == "1w":
        # Unix epoch began on Thursday; Monday 00:00 UTC is four days later.
        return (open_time_ms - 4 * 86_400_000) % duration == 0
    return open_time_ms % duration == 0


def _normalize_candle_sequence(rows: list[dict[str, Any]], interval: str) -> list[dict[str, Any]]:
    """Validate OHLCV values and exact timeframe duration before ordering candles."""
    if interval not in TIMEFRAMES:
        raise ValueError("Provider returned candles for an unsupported timeframe")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Provider returned an empty or invalid candle sequence")
    for row in rows:
        if not isinstance(row, dict) or not _is_valid_candle(row):
            raise ValueError("Provider returned an invalid OHLCV candle")
        if not _is_aligned_candle_open(row["open_time"], interval):
            raise ValueError("Provider candle open timestamp is not aligned to the UTC timeframe boundary")
        expected_close = row["open_time"] + _interval_duration_ms(interval, row["open_time"]) - 1
        if row["close_time"] != expected_close:
            raise ValueError("Provider candle timestamps do not match the requested timeframe")
    ordered = sorted(rows, key=lambda row: row["open_time"])
    for previous, current in zip(ordered, ordered[1:]):
        if current["open_time"] == previous["open_time"]:
            raise ValueError("Provider returned duplicate candle open timestamps")
        if previous["close_time"] >= current["open_time"]:
            raise ValueError("Provider returned overlapping candle time ranges")
    return ordered


def compare_provider_candles(
    provider_candles: dict[str, list[dict[str, Any]]],
    interval: str,
    price_tolerance_bps: float = 50.0,
    volume_tolerance_bps: float = 500.0,
) -> dict[str, Any]:
    """Compare same-market provider snapshots without fetching data or choosing a winner.

    Inputs must already represent the same symbol and quote asset. The report
    uses exact candle-open timestamp alignment and symmetric basis-point deltas.
    """
    if interval not in TIMEFRAMES:
        raise ValueError("Unsupported comparison interval")
    if not isinstance(provider_candles, dict) or len(provider_candles) < 2:
        raise ValueError("At least two named providers are required")
    try:
        price_tolerance_bps = float(price_tolerance_bps)
        volume_tolerance_bps = float(volume_tolerance_bps)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Tolerances must be finite non-negative numbers") from None
    if not math.isfinite(price_tolerance_bps) or price_tolerance_bps < 0:
        raise ValueError("Price tolerance must be a finite non-negative number")
    if not math.isfinite(volume_tolerance_bps) or volume_tolerance_bps < 0:
        raise ValueError("Volume tolerance must be a finite non-negative number")

    normalized: dict[str, dict[int, dict[str, Any]]] = {}
    for provider, rows in provider_candles.items():
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("Provider names must be non-empty strings")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{provider} must supply a non-empty candle list")
        by_time: dict[int, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict) or not _is_valid_candle(row):
                raise ValueError(f"{provider} supplied an invalid candle")
            timestamp = row["open_time"]
            if isinstance(timestamp, bool) or not isinstance(timestamp, int):
                raise ValueError(f"{provider} supplied a non-integer candle timestamp")
            if timestamp in by_time:
                raise ValueError(f"{provider} supplied duplicate candle timestamps")
            by_time[timestamp] = row
        normalized[provider] = by_time

    all_times = sorted({stamp for rows in normalized.values() for stamp in rows})
    expected_ms = _INTERVAL_MS[interval]
    timeline_gaps = []
    for previous, current in zip(all_times, all_times[1:]):
        expected_next = previous + _interval_duration_ms(interval, previous)
        if current > expected_next:
            timeline_gaps.append({
                "after_open_time": previous,
                "before_open_time": current,
                "missing_intervals": max(1, round((current - expected_next) / expected_ms)),
            })

    providers = {}
    for name, rows in normalized.items():
        missing = [stamp for stamp in all_times if stamp not in rows]
        providers[name] = {
            "candle_count": len(rows),
            "missing_timestamps": missing,
            "missing_timestamp_count": len(missing),
            "first_open_time": min(rows),
            "last_open_time": max(rows),
        }

    provider_missing_interval_count = sum(item["missing_timestamp_count"] for item in providers.values())

    pairwise = []
    names = sorted(normalized)
    for index, left_name in enumerate(names):
        for right_name in names[index + 1:]:
            left, right = normalized[left_name], normalized[right_name]
            shared = sorted(set(left) & set(right))
            price_deltas = []
            volume_deltas = []
            for stamp in shared:
                a, b = left[stamp], right[stamp]
                for field in ("open", "high", "low", "close"):
                    midpoint = (float(a[field]) + float(b[field])) / 2
                    delta = abs(float(a[field]) - float(b[field])) / midpoint * 10_000
                    price_deltas.append(delta)
                volume_midpoint = (float(a["volume"]) + float(b["volume"])) / 2
                if volume_midpoint > 0:
                    volume_deltas.append(abs(float(a["volume"]) - float(b["volume"])) / volume_midpoint * 10_000)
                elif float(a["volume"]) != float(b["volume"]):
                    volume_deltas.append(float("inf"))
                else:
                    volume_deltas.append(0.0)
            max_price = max(price_deltas, default=None)
            max_volume = max(volume_deltas, default=None)
            pairwise.append({
                "providers": [left_name, right_name],
                "shared_candle_count": len(shared),
                "price_discrepancy_bps_max": round(max_price, 4) if max_price is not None and math.isfinite(max_price) else max_price,
                "volume_discrepancy_bps_max": round(max_volume, 4) if max_volume is not None and math.isfinite(max_volume) else max_volume,
                "price_within_tolerance": max_price is not None and max_price <= price_tolerance_bps,
                "volume_within_tolerance": max_volume is not None and max_volume <= volume_tolerance_bps,
            })

    has_alignment = all(item["shared_candle_count"] > 0 for item in pairwise)
    within_tolerance = has_alignment and all(
        item["price_within_tolerance"] and item["volume_within_tolerance"] for item in pairwise
    )
    return {
        "mode": "read_only",
        "interval": interval,
        "provider_count": len(normalized),
        "providers": providers,
        "timeline_gaps": timeline_gaps,
        "timeline_gap_count": len(timeline_gaps),
        "provider_missing_interval_count": provider_missing_interval_count,
        "pairwise_comparisons": pairwise,
        "price_tolerance_bps": float(price_tolerance_bps),
        "volume_tolerance_bps": float(volume_tolerance_bps),
        "consistency_status": "consistent_within_configured_tolerances" if within_tolerance and not timeline_gaps and provider_missing_interval_count == 0 else (
            "insufficient_timestamp_overlap" if not has_alignment else "discrepancies_or_gaps_detected"
        ),
        "limitations": [
            "Inputs must represent the same symbol and quote asset; this helper does not verify market identity.",
            "Provider snapshots are compared at exact candle-open timestamps; differing candle boundaries are not interpolated.",
            "A tolerance result is a diagnostic, not proof that either provider is correct or independently audited.",
            "Monthly interval gap estimation uses a fixed-duration approximation for the missing-interval count.",
        ],
    }



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
    # Never substitute a USD market for a USDT request: quote assets are not interchangeable.
    if quote != "USD":
        raise ValueError("Coinbase fallback supports USD-quoted pairs only; USDT requests are not mapped to USD.")
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
                # fractional values, non-finite values, and unrepresentable dates.
                if isinstance(row[0], bool):
                    continue
                timestamp_seconds = float(row[0])
                if (
                    not math.isfinite(timestamp_seconds)
                    or not timestamp_seconds.is_integer()
                    or timestamp_seconds < 0
                    or timestamp_seconds * 1000 > MAX_TIMESTAMP_MS
                ):
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
    """Load one provider snapshot; only transport failures and HTTP 451 fail over."""
    fallback_reason = None
    try:
        rows = await asyncio.to_thread(_fetch_binance, symbol, interval, limit)
        source, endpoint = "Binance public market-data API", BINANCE_KLINES_URL
    except urllib.error.HTTPError as exc:
        if exc.code in (418, 429):
            raise HTTPException(status_code=503, detail="Public market-data rate limit reached; retry later.") from exc
        if exc.code != 451:
            raise HTTPException(status_code=502, detail=f"Binance public market-data provider returned HTTP {exc.code}.") from exc
        fallback_reason = "Binance HTTP 451"
    except (urllib.error.URLError, TimeoutError, OSError):
        fallback_reason = "Binance transport failure"

    if fallback_reason is not None:
        try:
            rows = await asyncio.to_thread(_fetch_kraken, symbol, interval, limit)
            source = f"Kraken public OHLC API (fallback after {fallback_reason})"
            endpoint = KRAKEN_OHLC_URL
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            try:
                rows = await asyncio.to_thread(_fetch_coinbase, symbol, interval, limit)
                source = f"Coinbase Exchange public candles API (fallback after {fallback_reason})"
                endpoint = COINBASE_CANDLES_URL
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as coinbase_exc:
                reason = "Kraken and Coinbase fallbacks unavailable or pair/timeframe unsupported"
                if isinstance(coinbase_exc, urllib.error.HTTPError):
                    reason += f" (Coinbase HTTP {coinbase_exc.code})"
                raise HTTPException(status_code=503, detail=reason + f"; {fallback_reason}.") from None

    try:
        rows = _normalize_candle_sequence(rows, interval)
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
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    freshness = _freshness_metadata(rows, interval, now_ms)
    timeline_integrity = _timeline_integrity_metadata(rows, interval)
    source = rows[0].get("_source", "Binance public market-data API")
    endpoint = rows[0].get("_source_endpoint", BINANCE_KLINES_URL)
    return {
        "service": "cin", "mode": "read_only", "source": source, "source_endpoint": endpoint,
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "symbol": normalized,
        "timeframe": interval, "count": len(rows),
        **freshness,
        "timeline_integrity": timeline_integrity,
        "data": [
            {
                **{key: value for key, value in row.items() if not key.startswith("_")},
                "open_time_utc": datetime.fromtimestamp(row["open_time"] / 1000, timezone.utc).isoformat(),
                "close_time_utc": datetime.fromtimestamp(row["close_time"] / 1000, timezone.utc).isoformat(),
                "is_closed": row["close_time"] < now_ms,
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
    try:
        analysis = analyze_ohlc([{key: row[key] for key in ("open", "high", "low", "close")} for row in closed_rows])
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Fetched candles failed analysis validation: {exc}") from exc
    analysis["input"].update({
        "symbol": normalized, "timeframe": interval, "source": source, "source_endpoint": endpoint,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "requested_candle_count": len(rows),
        "analysis_candle_count": len(closed_rows),
        "forming_candle_excluded_count": len(rows) - len(closed_rows),
        "candle_closure_policy": "technical analysis uses only candles whose close_time is earlier than retrieval time",
        "first_candle_open_time_utc": datetime.fromtimestamp(closed_rows[0]["open_time"] / 1000, timezone.utc).isoformat(),
        "last_candle_close_time_utc": datetime.fromtimestamp(closed_rows[-1]["close_time"] / 1000, timezone.utc).isoformat(),
        "volume_included_in_source_but_not_used_in_indicators": True,
        **freshness,
        "timeline_integrity": _timeline_integrity_metadata(rows, interval),
    })
    analysis["limitations"].extend([
        "Public exchange data is not independently audited by CIN.",
        "The market-candles endpoint labels forming candles; the technical-analysis endpoint excludes them.",
        "Technical outputs and ATR scenarios are descriptive research, not investment advice or trade instructions.",
    ])
    return analysis
