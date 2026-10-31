"""Coinbase Exchange public candle adapter for CIN (read-only, no credentials)."""
from __future__ import annotations

import json
import math
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

BASE_URL = "https://api.exchange.coinbase.com"
CANDLES_PATH = "/products/{product_id}/candles"
USER_AGENT = "CIN-Research-API/0.1.0"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_CANDLES_PER_REQUEST = 300
GRANULARITIES = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "1d": 86400,
}


def _validate_request(product_id: str, granularity: str, start: int, end: int) -> None:
    if not isinstance(product_id, str) or not re.fullmatch(r"[A-Z0-9]{2,12}-USD", product_id):
        raise ValueError("Coinbase product must be an explicitly USD-quoted product such as BTC-USD.")
    if granularity not in GRANULARITIES:
        raise ValueError("Unsupported Coinbase candle granularity.")
    if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int):
        raise ValueError("Candle start and end must be integer Unix timestamps in seconds.")
    if start < 0 or end <= start:
        raise ValueError("Candle time range is invalid.")
    if end - start > MAX_CANDLES_PER_REQUEST * GRANULARITIES[granularity]:
        raise ValueError("Coinbase candle request exceeds the 300-candle window limit.")
    try:
        datetime.fromtimestamp(start, timezone.utc)
        datetime.fromtimestamp(end, timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("Candle time range is outside the supported UTC timestamp range.") from exc


def _request_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={"accept": "application/json", "user-agent": USER_AGENT},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"Coinbase public market-data provider returned HTTP {response.status}.")
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Coinbase response exceeded the configured size limit.")
    return json.loads(body.decode("utf-8"))


def _finite_positive(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _normalize_rows_with_diagnostics(payload: Any, granularity: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if not isinstance(payload, list):
        raise ValueError("Coinbase candles response was not a list.")
    if len(payload) > MAX_CANDLES_PER_REQUEST:
        raise ValueError("Coinbase returned more than 300 candles.")
    duration_ms = GRANULARITIES[granularity] * 1000
    by_timestamp: dict[int, dict[str, Any]] = {}
    invalid_rows = 0
    duplicate_rows = 0
    valid_rows = 0
    for row in payload:
        if not isinstance(row, list) or len(row) != 6:
            invalid_rows += 1
            continue
        timestamp = row[0]
        if isinstance(timestamp, bool):
            invalid_rows += 1
            continue
        try:
            timestamp_float = float(timestamp)
            if not math.isfinite(timestamp_float) or not timestamp_float.is_integer():
                invalid_rows += 1
                continue
            timestamp_seconds = int(timestamp_float)
            # Coinbase row order is [time, low, high, open, close, volume].
            low = _finite_positive(row[1])
            high = _finite_positive(row[2])
            open_price = _finite_positive(row[3])
            close = _finite_positive(row[4])
            volume = float(row[5]) if not isinstance(row[5], bool) else math.nan
        except (TypeError, ValueError, OverflowError):
            invalid_rows += 1
            continue
        if (
            min(timestamp_seconds, 0) < 0
            or any(value is None for value in (low, high, open_price, close))
            or not math.isfinite(volume) or volume < 0
            or high < max(open_price, close, low)
            or low > min(open_price, close)
        ):
            invalid_rows += 1
            continue
        valid_rows += 1
        open_ms = timestamp_seconds * 1000
        if timestamp_seconds in by_timestamp:
            duplicate_rows += 1
        by_timestamp[timestamp_seconds] = {
            "open_time": open_ms,
            "close_time": open_ms + duration_ms - 1,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    rows = [by_timestamp[key] for key in sorted(by_timestamp)]
    if not rows:
        raise ValueError("Coinbase returned no valid candles.")
    diagnostics = {
        "provider_rows_received": len(payload),
        "provider_rows_invalid": invalid_rows,
        "provider_rows_duplicate": duplicate_rows,
        "provider_rows_valid_before_deduplication": valid_rows,
        "normalized_rows_count": len(rows),
    }
    return rows, diagnostics


def _normalize_rows(payload: Any, granularity: str) -> list[dict[str, Any]]:
    rows, _ = _normalize_rows_with_diagnostics(payload, granularity)
    return rows


def fetch_candles_with_diagnostics(product_id: str, granularity: str, start: int, end: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    _validate_request(product_id, granularity, start, end)
    query = urllib.parse.urlencode({
        "granularity": GRANULARITIES[granularity],
        "start": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "end": datetime.fromtimestamp(end, timezone.utc).isoformat(),
    })
    encoded_product = urllib.parse.quote(product_id, safe="")
    url = f"{BASE_URL}{CANDLES_PATH.format(product_id=encoded_product)}?{query}"
    return _normalize_rows_with_diagnostics(_request_json(url), granularity)


def fetch_candles(product_id: str, granularity: str, start: int, end: int) -> list[dict[str, Any]]:
    """Fetch one bounded UTC candle window from Coinbase Exchange public API.

    Product IDs are passed as explicit USD-quoted identifiers. Quote currencies
    are never silently converted (for example, BTC-USDT is not BTC-USD).
    """
    rows, _ = fetch_candles_with_diagnostics(product_id, granularity, start, end)
    return rows
