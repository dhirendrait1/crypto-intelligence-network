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
KRAKEN_ASSET_PAIRS_URL = "https://api.kraken.com/0/public/AssetPairs"
MAX_KRAKEN_OHLC_ROWS = 720
MAX_BINANCE_KLINE_LIMIT = 1000
MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024
# Largest millisecond Unix timestamp representable by Python datetime (year 9999).
MAX_TIMESTAMP_MS = 253402300799999


class _MalformedProviderResponse(ValueError):
    """A successful provider payload contains a malformed candle row."""
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
    if not isinstance(rows, list) or not rows:
        raise ValueError("Timeline requires a non-empty candle list")
    for row in rows:
        if (
            not isinstance(row, dict)
            or isinstance(row.get("open_time"), bool)
            or not isinstance(row.get("open_time"), int)
        ):
            raise ValueError("Timeline contains an invalid candle open timestamp")
    ordered = sorted(rows, key=lambda row: row["open_time"])
    gaps = []
    missing_total = 0
    for previous, current in zip(ordered, ordered[1:]):
        expected = previous["open_time"] + _interval_duration_ms(interval, previous["open_time"])
        if current["open_time"] < expected:
            raise ValueError("Timeline contains duplicate or overlapping candle intervals")
        if current["open_time"] == expected:
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


def _expected_window_opens(interval: str, requested_limit: int, provider: str, now_ms: int) -> list[int]:
    """Build provider-aligned expected candle opens ending at the current interval."""
    if interval not in TIMEFRAMES or provider not in {"binance", "kraken", "coinbase"}:
        raise ValueError("Unsupported provider/timeframe window")
    if provider == "coinbase" and interval == "1w":
        raise ValueError("Coinbase weekly candle boundary is not supported")
    if provider != "binance" and interval == "3d":
        raise ValueError("Three-day candle boundary is not supported by this provider")
    if interval == "1M":
        if provider != "binance":
            raise ValueError("Monthly candle boundary is not supported by this provider")
        current = datetime.fromtimestamp(now_ms / 1000, timezone.utc)
        cursor = int(datetime(current.year, current.month, 1, tzinfo=timezone.utc).timestamp() * 1000)
    else:
        duration = _INTERVAL_MS[interval]
        anchor_ms = 4 * 86_400_000 if interval == "1w" and provider == "binance" else 0
        cursor = ((now_ms - anchor_ms) // duration) * duration + anchor_ms
    opens = [cursor]
    for _ in range(requested_limit - 1):
        previous = opens[-1]
        if interval == "1M":
            current = datetime.fromtimestamp(previous / 1000, timezone.utc)
            if current.month == 1:
                previous = int(datetime(current.year - 1, 12, 1, tzinfo=timezone.utc).timestamp() * 1000)
            else:
                previous = int(datetime(current.year, current.month - 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        else:
            previous -= _INTERVAL_MS[interval]
        opens.append(previous)
    return list(reversed(opens))


def _historical_window_integrity_metadata(
    rows: list[dict[str, Any]], interval: str, requested_limit: int,
    provider: str, now_ms: int,
) -> dict[str, Any]:
    """Report missing leading/trailing opens in the requested rolling window without imputing them."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("Historical window requires non-empty candles")
    if isinstance(requested_limit, bool) or not isinstance(requested_limit, int) or requested_limit < 1:
        raise ValueError("Historical window requires a positive integer request limit")
    expected = _expected_window_opens(interval, requested_limit, provider, now_ms)
    actual = []
    for row in rows:
        if not isinstance(row, dict) or isinstance(row.get("open_time"), bool) or not isinstance(row.get("open_time"), int):
            raise ValueError("Historical window contains an invalid candle open timestamp")
        actual.append(row["open_time"])
    if actual != sorted(actual) or len(actual) != len(set(actual)):
        raise ValueError("Historical window candle opens must be unique and chronological")
    expected_set = set(expected)
    in_window = [stamp for stamp in actual if stamp in expected_set]
    leading = 0
    for stamp in expected:
        if stamp in set(in_window):
            break
        leading += 1
    trailing = 0
    for stamp in reversed(expected):
        if stamp in set(in_window):
            break
        trailing += 1
    outside = [stamp for stamp in actual if stamp not in expected_set]
    complete = leading == 0 and trailing == 0 and not outside
    return {
        "window_status": "complete" if complete else "partial",
        "provider": provider,
        "requested_interval_count": requested_limit,
        "expected_window_start_open_time_utc": datetime.fromtimestamp(expected[0] / 1000, timezone.utc).isoformat(),
        "expected_window_end_open_time_utc": datetime.fromtimestamp(expected[-1] / 1000, timezone.utc).isoformat(),
        "leading_missing_interval_count": leading,
        "trailing_missing_interval_count": trailing,
        "out_of_window_candle_count": len(outside),
        "observed_in_window_candle_count": len(in_window),
        "window_warning": None if complete else "Requested window has missing edge intervals or out-of-window rows; provider-specific no-trade omissions may explain some absences.",
        "interpretation_scope": "requested_rolling_window_edges_only; not_proof_of_provider_feed_loss",
        "missing_candles_synthesized": False,
    }


def _coverage_metadata(rows: list[dict[str, Any]], requested_limit: int) -> dict[str, Any]:
    """Report returned row count against the requested limit, not continuity."""
    if (
        not isinstance(rows, list)
        or isinstance(requested_limit, bool)
        or not isinstance(requested_limit, int)
        or requested_limit < 1
    ):
        raise ValueError("Coverage requires a candle list and a positive integer request limit")
    returned_count = len(rows)
    first_open = rows[0]["open_time"] if rows else None
    last_open = rows[-1]["open_time"] if rows else None
    shortfall = max(0, requested_limit - returned_count)
    ratio = min(1.0, returned_count / requested_limit)
    return {
        "requested_candle_limit": requested_limit,
        "returned_candle_count": returned_count,
        "candle_count_shortfall": shortfall,
        "returned_row_ratio": round(ratio, 4),
        "coverage_status": "complete" if shortfall == 0 else "partial",
        "coverage_warning": (
            None if shortfall == 0 else
            "Provider returned fewer rows than requested; inspect timeline_integrity and provider semantics before interpreting the shortfall."
        ),
        "first_returned_candle_open_time_utc": (
            datetime.fromtimestamp(first_open / 1000, timezone.utc).isoformat()
            if first_open is not None else None
        ),
        "last_returned_candle_open_time_utc": (
            datetime.fromtimestamp(last_open / 1000, timezone.utc).isoformat()
            if last_open is not None else None
        ),
        "coverage_scope": "returned_row_count_against_requested_limit_only; not_a_continuity_or_feed_health_claim",
    }


def _volume_quality_metadata(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe zero-volume runs and ranked volume changes without threshold-based rejection."""
    volumes = [float(row["volume"]) for row in rows]
    zero_indices = [index for index, value in enumerate(volumes) if value == 0]
    positive = sorted(value for value in volumes if value > 0)
    if positive:
        middle = len(positive) // 2
        median_positive = (
            positive[middle] if len(positive) % 2
            else (positive[middle - 1] + positive[middle]) / 2
        )
    else:
        median_positive = None

    zero_runs = []
    run_start = None
    for index, value in enumerate(volumes + [None]):
        if value == 0 and run_start is None:
            run_start = index
        elif value != 0 and run_start is not None:
            zero_runs.append({
                "start_open_time": rows[run_start]["open_time"],
                "end_open_time": rows[index - 1]["open_time"],
                "candle_count": index - run_start,
            })
            run_start = None

    transitions = []
    for index in range(1, len(volumes)):
        previous, current = volumes[index - 1], volumes[index]
        if previous == current:
            continue
        if previous == 0:
            classification, ratio = "zero_to_positive" if current > 0 else "zero_to_zero", None
        elif current == 0:
            classification, ratio = "positive_to_zero", 0.0
        else:
            classification, ratio = "positive_to_positive", round(current / previous, 8)
        transitions.append({
            "from_open_time": rows[index - 1]["open_time"],
            "to_open_time": rows[index]["open_time"],
            "previous_volume": previous,
            "current_volume": current,
            "transition": classification,
            "current_to_previous_ratio": ratio,
        })
    ranked_transitions = sorted(
        transitions,
        key=lambda item: (
            item["transition"] in {"zero_to_positive", "positive_to_zero"},
            abs(math.log(item["current_to_previous_ratio"]))
            if item["current_to_previous_ratio"] not in (None, 0) else float("inf"),
        ),
        reverse=True,
    )[:5]
    median_ranked = []
    if median_positive is not None:
        median_ranked = sorted(
            [{
                "open_time": row["open_time"],
                "volume": float(row["volume"]),
                "ratio_to_positive_volume_median": round(float(row["volume"]) / median_positive, 8),
            } for row in rows if float(row["volume"]) > 0],
            key=lambda item: item["ratio_to_positive_volume_median"],
            reverse=True,
        )[:5]
    return {
        "volume_field_missing_count": 0,
        "zero_volume_candle_count": len(zero_indices),
        "zero_volume_run_count": len(zero_runs),
        "zero_volume_runs": zero_runs,
        "positive_volume_median": median_positive,
        "largest_volume_ratios_to_positive_median": median_ranked,
        "largest_adjacent_volume_transitions": ranked_transitions,
        "volume_change_interpretation": "ranked_observations_only_no_spike_threshold_or_feed_failure_inference",
    }


def _provider_volume_semantics(provider: str) -> dict[str, Any]:
    """Describe documented raw candle-volume semantics without guessing units."""
    descriptors = {
        "binance": {
            "provider": "binance",
            "source_field": "kline[5]",
            "source_field_label": "Volume",
            "unit_basis": "base_asset",
            "unit_asset": "market_base_asset",
            "evidence_status": "provider_schema_distinguishes_volume_from_quote_asset_volume",
            "provenance": "Binance Spot REST klines response schema",
            "independent_unit_verification": True,
        },
        "kraken": {
            "provider": "kraken",
            "source_field": "ohlc_row[6]",
            "source_field_label": "volume",
            "unit_basis": "unknown",
            "unit_asset": None,
            "evidence_status": "response_schema_labels_volume_but_does_not_specify_asset_basis",
            "provenance": "Kraken Spot REST OHLC response schema",
            "independent_unit_verification": False,
        },
        "coinbase": {
            "provider": "coinbase",
            "source_field": "candle_row[5]",
            "source_field_label": "volume",
            "unit_basis": "unknown",
            "unit_asset": None,
            "evidence_status": "response_schema_labels_volume_but_does_not_specify_asset_basis",
            "provenance": "Coinbase Exchange REST product candles response schema",
            "independent_unit_verification": False,
        },
    }
    if provider not in descriptors:
        return {
            "provider": provider,
            "source_field": None,
            "source_field_label": None,
            "unit_basis": "unknown",
            "unit_asset": None,
            "evidence_status": "unsupported_provider_semantics",
            "provenance": None,
            "independent_unit_verification": False,
        }
    return dict(descriptors[provider])


def _provider_data_quality_metadata(rows: list[dict[str, Any]], interval: str, now_ms: int) -> dict[str, Any]:
    """Summarize candle validity, forming-tail status, and freshness without repairing data."""
    if interval not in TIMEFRAMES:
        raise ValueError("Unsupported data-quality interval")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Data-quality assessment requires non-empty candles")
    seen_open_times = set()
    for row in rows:
        if not isinstance(row, dict) or not _is_valid_candle(row):
            raise ValueError("Provider returned an invalid OHLCV candle")
        open_time = row["open_time"]
        if open_time > now_ms:
            raise ValueError("Provider returned a candle with a future open timestamp")
        if open_time in seen_open_times:
            raise ValueError("Provider returned duplicate candle open timestamps")
        seen_open_times.add(open_time)
    if any(
        current["open_time"] < previous["open_time"]
        for previous, current in zip(rows, rows[1:])
    ):
        raise ValueError("Provider candle timestamps are not chronological")
    ordered = list(rows)
    freshness = _freshness_metadata(ordered, interval, now_ms)
    forming = [row for row in ordered if row["close_time"] >= now_ms]
    volume_quality = _volume_quality_metadata(ordered)
    zero_volume_count = volume_quality["zero_volume_candle_count"]
    warnings = []
    if freshness["is_stale"]:
        warnings.append("latest_completed_candle_is_stale")
    if forming:
        warnings.append("latest_candle_may_be_forming")
    if zero_volume_count:
        warnings.append("zero_volume_candles_present_review_provider_semantics")
    return {
        "quality_status": "warning" if warnings else "ok",
        "candle_count": len(ordered),
        "completed_candle_count": len(ordered) - len(forming),
        "forming_candle_count": len(forming),
        "latest_candle_is_forming": bool(forming and forming[-1] is ordered[-1]),
        "zero_volume_candle_count": zero_volume_count,
        "volume_quality": volume_quality,
        "invalid_candle_count": 0,
        "freshness_status": freshness["freshness_status"],
        "latest_completed_candle_age_seconds": freshness["latest_closed_candle_age_seconds"],
        "warnings": warnings,
        "data_repaired_or_synthesized": False,
    }


def _freshness_metadata(rows: list[dict[str, Any]], interval: str, now_ms: int) -> dict[str, Any]:
    """Report completed-candle freshness and reject candles opening in the future."""
    if any(row["open_time"] > now_ms for row in rows):
        raise ValueError("Provider returned a candle with a future open timestamp")
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



def _kraken_request_json(url: str) -> Any:
    """Classify invalid successful Kraken response bodies as malformed, not outages."""
    try:
        return _request_json(url)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        raise _MalformedProviderResponse("Kraken returned an invalid successful response body") from None


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
    # Binance Spot REST permits at most 1000 klines per request. The public
    # CIN route is stricter (5–500); keep this adapter safe for direct callers.
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_BINANCE_KLINE_LIMIT:
        raise ValueError("Binance candle request limit must be an integer from 1 to 1000")
    query = urllib.parse.urlencode({"symbol": symbol, "interval": interval, "limit": limit})
    payload = _request_json(f"{BINANCE_KLINES_URL}?{query}")
    if not isinstance(payload, list):
        raise ValueError("Binance response was not a list")
    if len(payload) > limit:
        raise ValueError("Binance returned more candles than requested")
    candles = []
    for row in payload:
        if not isinstance(row, list) or len(row) < 7:
            raise _MalformedProviderResponse("Binance returned a malformed candle row")
        try:
            # Do not silently discard malformed source rows or truncate timestamps.
            if isinstance(row[0], bool) or isinstance(row[6], bool):
                raise _MalformedProviderResponse("Binance returned a boolean candle timestamp")
            open_time_value, close_time_value = float(row[0]), float(row[6])
            if not open_time_value.is_integer() or not close_time_value.is_integer():
                raise _MalformedProviderResponse("Binance returned a fractional candle timestamp")
            candle = {
                "open_time": int(open_time_value), "open": float(row[1]), "high": float(row[2]),
                "low": float(row[3]), "close": float(row[4]), "volume": float(row[5]),
                "close_time": int(close_time_value),
            }
            if not _is_valid_candle(candle):
                raise _MalformedProviderResponse("Binance returned invalid OHLCV values")
            candles.append(candle)
        except _MalformedProviderResponse:
            raise
        except (TypeError, ValueError, OverflowError):
            raise _MalformedProviderResponse("Binance returned a malformed candle row") from None
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
    # Resolve the requested base/quote against Kraken's public market catalogue.
    # AssetPairs exposes the canonical result key, altname, and websocket name;
    # use its exact altname for OHLC and verify the returned key against that record.
    requested_pair = f"{base}{quote}"
    pair_query = urllib.parse.urlencode({"pair": requested_pair})
    pair_payload = _kraken_request_json(f"{KRAKEN_ASSET_PAIRS_URL}?{pair_query}")
    if not isinstance(pair_payload, dict):
        raise _MalformedProviderResponse("Kraken AssetPairs response was not an object")
    pair_errors = pair_payload.get("error")
    if not isinstance(pair_errors, list) or pair_errors:
        raise _MalformedProviderResponse("Kraken AssetPairs returned an invalid error envelope")
    pair_result = pair_payload.get("result")
    if not isinstance(pair_result, dict) or len(pair_result) != 1:
        raise _MalformedProviderResponse("Kraken AssetPairs did not resolve exactly one requested market")
    canonical_key, pair_info = next(iter(pair_result.items()))
    if not isinstance(pair_info, dict):
        raise _MalformedProviderResponse("Kraken AssetPairs returned invalid market metadata")
    altname = pair_info.get("altname")
    wsname = pair_info.get("wsname")
    expected_wsname = f"{base}/{quote}"
    if (
        not isinstance(altname, str)
        or altname.upper() != requested_pair
        or not isinstance(wsname, str)
        or wsname.upper() != expected_wsname
    ):
        raise _MalformedProviderResponse("Kraken AssetPairs base/quote identity did not match the requested market")
    query = urllib.parse.urlencode({"pair": altname, "interval": KRAKEN_INTERVALS[interval]})
    payload = _kraken_request_json(f"{KRAKEN_OHLC_URL}?{query}")
    if not isinstance(payload, dict):
        raise _MalformedProviderResponse("Kraken response was not an object")
    errors = payload.get("error")
    if not isinstance(errors, list):
        raise _MalformedProviderResponse("Kraken OHLC response had an invalid error envelope")
    if errors:
        raise ValueError("Kraken rejected pair/timeframe: " + "; ".join(str(e) for e in errors))
    result = payload.get("result")
    if not isinstance(result, dict) or "last" not in result:
        raise _MalformedProviderResponse("Kraken OHLC response had no result or pagination cursor")
    cursor = result.get("last")
    if isinstance(cursor, bool):
        raise _MalformedProviderResponse("Kraken OHLC pagination cursor was not an integer Unix timestamp")
    try:
        cursor_value = float(cursor)
    except (TypeError, ValueError, OverflowError):
        raise _MalformedProviderResponse("Kraken OHLC pagination cursor was not an integer Unix timestamp") from None
    if not math.isfinite(cursor_value) or not cursor_value.is_integer() or cursor_value < 0:
        raise _MalformedProviderResponse("Kraken OHLC pagination cursor was not an integer Unix timestamp")
    cursor_seconds = int(cursor_value)
    pair_keys = [key for key in result if key != "last"]
    accepted_keys = {canonical_key, altname, wsname.replace("/", "")}
    if len(pair_keys) != 1 or pair_keys[0] not in accepted_keys:
        raise _MalformedProviderResponse("Kraken OHLC result key did not match the resolved requested market")
    pair_key = pair_keys[0]
    rows = result.get(pair_key)
    if not isinstance(rows, list):
        raise _MalformedProviderResponse("Kraken returned no candle rows")
    # Kraken's REST OHLC endpoint is capped at 720 time steps and always
    # includes the current, not-yet-committed frame. The public API route caps
    # requested history at 500, so one bounded response is sufficient; never
    # silently truncate an unexpectedly oversized provider payload.
    if len(rows) > MAX_KRAKEN_OHLC_ROWS:
        raise _MalformedProviderResponse("Kraken returned more OHLC rows than its documented 720-row cap")
    candles = []
    # Validate rows before applying the requested limit so malformed tail rows
    # do not unnecessarily reduce the number of usable recent candles.
    for row in rows:
        if not isinstance(row, list) or len(row) < 7:
            raise _MalformedProviderResponse("Kraken returned a malformed candle row")
        try:
            # Reject malformed timestamps and values; do not silently understate
            # provider row counts by dropping invalid source rows.
            if isinstance(row[0], bool):
                raise _MalformedProviderResponse("Kraken returned a boolean candle timestamp")
            start_seconds = float(row[0])
            if not math.isfinite(start_seconds) or not start_seconds.is_integer():
                raise _MalformedProviderResponse("Kraken returned a fractional or non-finite candle timestamp")
            start = int(start_seconds * 1000)
            if not _is_aligned_candle_open(start, interval, "kraken"):
                raise _MalformedProviderResponse(
                    "Kraken returned a candle open outside its UTC timeframe boundary"
                )
            duration_ms = KRAKEN_INTERVALS[interval] * 60_000
            if duration_ms != _interval_duration_ms(interval, start):
                raise _MalformedProviderResponse(
                    "Kraken interval duration does not match the supported UTC timeframe"
                )
            candle = {
                "open_time": start, "open": float(row[1]), "high": float(row[2]),
                "low": float(row[3]), "close": float(row[4]), "volume": float(row[6]),
                "close_time": start + duration_ms - 1,
            }
            if not _is_valid_candle(candle):
                raise _MalformedProviderResponse("Kraken returned invalid OHLCV values")
            if candles and start <= candles[-1]["open_time"]:
                raise _MalformedProviderResponse(
                    "Kraken returned duplicate or out-of-order candle timestamps"
                )
            candles.append(candle)
        except _MalformedProviderResponse:
            raise
        except (TypeError, ValueError, OverflowError):
            raise _MalformedProviderResponse("Kraken returned a malformed candle row") from None
    if not candles:
        raise ValueError("Kraken returned no valid candles")
    if cursor_seconds < max(row["open_time"] // 1000 for row in candles):
        raise _MalformedProviderResponse("Kraken OHLC pagination cursor precedes the latest returned candle")
    return candles[-limit:]


def _is_aligned_candle_open(open_time_ms: int, interval: str, provider: str = "binance") -> bool:
    """Check known provider-specific UTC candle boundaries for 24/7 crypto markets."""
    if (
        interval not in TIMEFRAMES
        or provider not in {"binance", "kraken", "coinbase"}
        or isinstance(open_time_ms, bool)
        or not isinstance(open_time_ms, int)
    ):
        return False
    if interval == "1M":
        if provider != "binance":
            return False
        value = datetime.fromtimestamp(open_time_ms / 1000, timezone.utc)
        return value.day == 1 and value.hour == value.minute == value.second == value.microsecond == 0
    if interval == "1w":
        if provider == "coinbase":
            return False
        # Binance weeks open Monday 00:00 UTC; Kraken weeks open Thursday 00:00 UTC.
        anchor_ms = 4 * 86_400_000 if provider == "binance" else 0
        return (open_time_ms - anchor_ms) % _INTERVAL_MS[interval] == 0
    # Binance documents UTC intervals but does not specify a distinct 3d anchor;
    # retain the current epoch-based fixed-duration check pending provider evidence.
    if interval == "3d" and provider != "binance":
        return False
    return open_time_ms % _INTERVAL_MS[interval] == 0


def _normalize_candle_sequence(
    rows: list[dict[str, Any]], interval: str, provider: str = "binance"
) -> list[dict[str, Any]]:
    """Validate OHLCV values and exact timeframe duration before ordering candles."""
    if interval not in TIMEFRAMES:
        raise ValueError("Provider returned candles for an unsupported timeframe")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Provider returned an empty or invalid candle sequence")
    for row in rows:
        if not isinstance(row, dict) or not _is_valid_candle(row):
            raise ValueError("Provider returned an invalid OHLCV candle")
        if not _is_aligned_candle_open(row["open_time"], interval, provider):
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
    market_identity_by_provider: dict[str, dict[str, str]] | None = None,
    volume_unit_by_provider: dict[str, str] | None = None,
    volume_semantics_by_provider: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare same-market provider snapshots without fetching data or choosing a winner.

    Inputs must already represent the same symbol and quote asset. The report
    uses exact candle-open timestamp alignment and symmetric basis-point deltas.
    """
    if interval not in TIMEFRAMES:
        raise ValueError("Unsupported comparison interval")
    if not isinstance(provider_candles, dict) or len(provider_candles) < 2:
        raise ValueError("At least two named providers are required")
    normalized_market_identities = None
    if market_identity_by_provider is not None:
        if not isinstance(market_identity_by_provider, dict):
            raise ValueError("Market identities must be supplied as a provider mapping")
        if set(market_identity_by_provider) != set(provider_candles):
            raise ValueError("Market identity entries must match the compared provider names")
        normalized_market_identities = {}
        for provider_name, identity in market_identity_by_provider.items():
            if not isinstance(identity, dict):
                raise ValueError("Each provider market identity must be an object")
            base_asset = identity.get("base_asset")
            quote_asset = identity.get("quote_asset")
            if (
                not isinstance(base_asset, str) or not re.fullmatch(r"[A-Z0-9]{2,20}", base_asset)
                or not isinstance(quote_asset, str) or not re.fullmatch(r"[A-Z0-9]{2,20}", quote_asset)
            ):
                raise ValueError("Market identity requires valid base_asset and quote_asset values")
            normalized_market_identities[provider_name] = (base_asset, quote_asset)
        if len(set(normalized_market_identities.values())) != 1:
            raise ValueError("Provider market identities do not match: base/quote assets differ")
    normalized_volume_units = None
    if volume_unit_by_provider is not None:
        if not isinstance(volume_unit_by_provider, dict) or set(volume_unit_by_provider) != set(provider_candles):
            raise ValueError("Volume units must be supplied for exactly the compared providers")
        normalized_volume_units = {}
        for provider_name, unit in volume_unit_by_provider.items():
            if not isinstance(unit, str) or not re.fullmatch(r"[A-Za-z0-9_./-]{1,40}", unit.strip()):
                raise ValueError("Each provider volume unit must be a non-empty explicit identifier")
            normalized_volume_units[provider_name] = unit.strip().upper()
    caller_declared_units_match = (
        normalized_volume_units is not None
        and len(set(normalized_volume_units.values())) == 1
    )
    normalized_volume_semantics = None
    volume_units_comparable = False
    if volume_semantics_by_provider is not None:
        if (
            not isinstance(volume_semantics_by_provider, dict)
            or set(volume_semantics_by_provider) != set(provider_candles)
        ):
            raise ValueError("Volume semantics must be supplied for exactly the compared providers")
        normalized_volume_semantics = {}
        verified_units = []
        for provider_name, descriptor in volume_semantics_by_provider.items():
            provider_key = provider_name.strip().lower() if isinstance(provider_name, str) else ""
            expected = _provider_volume_semantics(provider_key)
            if not isinstance(descriptor, dict):
                raise ValueError("Each provider volume semantics descriptor must be an object")
            # Accept only the exact source descriptor maintained by CIN's provider registry.
            if descriptor != expected:
                raise ValueError("Volume semantics descriptor does not match CIN's provider evidence registry")
            normalized_volume_semantics[provider_name] = dict(descriptor)
            if (
                descriptor.get("independent_unit_verification") is True
                and descriptor.get("unit_basis") in {"base_asset", "quote_asset"}
                and isinstance(descriptor.get("unit_asset"), str)
            ):
                verified_units.append((descriptor["unit_basis"], descriptor["unit_asset"].upper()))
            else:
                verified_units.append(None)
        if (
            normalized_market_identities is not None
            and all(unit is not None for unit in verified_units)
            and len(set(verified_units)) == 1
            and all(
                unit[1] == normalized_market_identities[provider_name][0 if unit[0] == "base_asset" else 1]
                for provider_name, unit in zip(provider_candles, verified_units)
            )
        ):
            volume_units_comparable = True
    volume_comparability_status = (
        "source_verified_common_unit" if volume_units_comparable else
        "caller_declared_matching_unit_only" if caller_declared_units_match else
        "unverified_or_incompatible_units"
    )

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
            provider_key = provider.strip().lower()
            declared_provider = row.get("_provider")
            if provider_key in {"binance", "kraken", "coinbase"} and declared_provider is not None:
                if not isinstance(declared_provider, str) or declared_provider.strip().lower() != provider_key:
                    raise ValueError(
                        f"{provider} snapshot contains a candle with mismatched provider provenance"
                    )
            timestamp = row["open_time"]
            if isinstance(timestamp, bool) or not isinstance(timestamp, int):
                raise ValueError(f"{provider} supplied a non-integer candle timestamp")
            if timestamp in by_time:
                raise ValueError(f"{provider} supplied duplicate candle timestamps")
            expected_close = timestamp + _interval_duration_ms(interval, timestamp) - 1
            if row["close_time"] != expected_close:
                raise ValueError(f"{provider} supplied a candle with an invalid timeframe duration")
            provider_key = provider.strip().lower()
            if provider_key in {"binance", "kraken", "coinbase"} and not _is_aligned_candle_open(
                timestamp, interval, provider_key
            ):
                raise ValueError(f"{provider} supplied a candle open outside its provider timeframe boundary")
            by_time[timestamp] = row
        normalized[provider] = by_time

    all_times = sorted({stamp for rows in normalized.values() for stamp in rows})
    timeline_gaps = []
    for previous, current in zip(all_times, all_times[1:]):
        expected_next = previous + _interval_duration_ms(interval, previous)
        if current > expected_next:
            cursor, missing = expected_next, 0
            while cursor < current:
                missing += 1
                cursor += _interval_duration_ms(interval, cursor)
            if cursor != current:
                raise ValueError("Provider comparison timestamps do not align to the requested interval")
            timeline_gaps.append({
                "after_open_time": previous,
                "before_open_time": current,
                "missing_intervals": missing,
            })

    providers = {}
    for name, rows in normalized.items():
        missing = [stamp for stamp in all_times if stamp not in rows]
        first_open, last_open = min(rows), max(rows)
        leading_missing = [stamp for stamp in missing if stamp < first_open]
        trailing_missing = [stamp for stamp in missing if stamp > last_open]
        internal_missing = [stamp for stamp in missing if first_open < stamp < last_open]
        providers[name] = {
            "candle_count": len(rows),
            "missing_timestamps": missing,
            "missing_timestamp_count": len(missing),
            "leading_window_mismatch_count": len(leading_missing),
            "trailing_window_mismatch_count": len(trailing_missing),
            "internal_missing_timestamp_count": len(internal_missing),
            "snapshot_union_coverage_ratio": round(len(rows) / len(all_times), 4) if all_times else 0.0,
            "first_open_time": first_open,
            "last_open_time": last_open,
            "first_open_time_utc": datetime.fromtimestamp(first_open / 1000, timezone.utc).isoformat(),
            "last_open_time_utc": datetime.fromtimestamp(last_open / 1000, timezone.utc).isoformat(),
        }

    provider_missing_interval_count = sum(item["missing_timestamp_count"] for item in providers.values())

    pairwise = []
    names = sorted(normalized)
    for index, left_name in enumerate(names):
        for right_name in names[index + 1:]:
            left, right = normalized[left_name], normalized[right_name]
            shared = sorted(set(left) & set(right))
            price_deltas = []
            price_observations = []
            left_right_price_ratios = []
            volume_deltas = []
            volume_observations = []
            zero_positive_volume_mismatch_count = 0
            for stamp in shared:
                a, b = left[stamp], right[stamp]
                for field in ("open", "high", "low", "close"):
                    left_price, right_price = float(a[field]), float(b[field])
                    midpoint = (left_price + right_price) / 2
                    delta = abs(left_price - right_price) / midpoint * 10_000
                    price_deltas.append(delta)
                    left_right_price_ratios.append(left_price / right_price)
                    price_observations.append({
                        "open_time": stamp,
                        "field": field,
                        "left_price": left_price,
                        "right_price": right_price,
                        "left_to_right_ratio": round(left_price / right_price, 8),
                        "discrepancy_bps": round(delta, 4),
                    })
                if volume_units_comparable:
                    left_volume, right_volume = float(a["volume"]), float(b["volume"])
                    volume_midpoint = (left_volume + right_volume) / 2
                    if volume_midpoint > 0:
                        volume_delta = abs(left_volume - right_volume) / volume_midpoint * 10_000
                    else:
                        volume_delta = 0.0
                    one_sided_zero = (left_volume == 0) != (right_volume == 0)
                    if one_sided_zero:
                        zero_positive_volume_mismatch_count += 1
                        volume_deltas.append(float("inf"))
                    else:
                        volume_deltas.append(volume_delta)
                    volume_observations.append({
                        "open_time": stamp,
                        "left_volume": left_volume,
                        "right_volume": right_volume,
                        "left_to_right_ratio": round(left_volume / right_volume, 8) if right_volume > 0 else None,
                        "symmetric_discrepancy_bps": (
                            round(volume_delta, 4) if math.isfinite(volume_delta) and not one_sided_zero else None
                        ),
                        "volume_pattern": (
                            "zero_vs_positive" if one_sided_zero else
                            "both_zero" if left_volume == 0 and right_volume == 0 else
                            "both_positive"
                        ),
                    })
            max_price = max(price_deltas, default=None)
            max_volume = max(volume_deltas, default=None)
            ordered_ratios = sorted(left_right_price_ratios)
            if ordered_ratios:
                middle = len(ordered_ratios) // 2
                median_ratio = (
                    ordered_ratios[middle] if len(ordered_ratios) % 2
                    else (ordered_ratios[middle - 1] + ordered_ratios[middle]) / 2
                )
                price_ratio_summary = {
                    "left_to_right_min": round(ordered_ratios[0], 8),
                    "left_to_right_median": round(median_ratio, 8),
                    "left_to_right_max": round(ordered_ratios[-1], 8),
                    "max_to_min_ratio_spread": round(ordered_ratios[-1] / ordered_ratios[0], 8),
                }
            else:
                price_ratio_summary = None
            largest_volume_discrepancies = sorted(
                volume_observations,
                key=lambda item: (
                    item["volume_pattern"] == "zero_vs_positive",
                    item["symmetric_discrepancy_bps"] if item["symmetric_discrepancy_bps"] is not None else float("inf"),
                ),
                reverse=True,
            )[:5] if volume_units_comparable else None
            largest_price_discrepancies = sorted(
                price_observations,
                key=lambda item: item["discrepancy_bps"],
                reverse=True,
            )[:5]
            left_only = sorted(set(left) - set(right))
            right_only = sorted(set(right) - set(left))
            pairwise.append({
                "providers": [left_name, right_name],
                "left_only_candle_count": len(left_only),
                "right_only_candle_count": len(right_only),
                "left_only_before_shared_window_count": sum(stamp < shared[0] for stamp in left_only) if shared else len(left_only),
                "left_only_after_shared_window_count": sum(stamp > shared[-1] for stamp in left_only) if shared else 0,
                "right_only_before_shared_window_count": sum(stamp < shared[0] for stamp in right_only) if shared else len(right_only),
                "right_only_after_shared_window_count": sum(stamp > shared[-1] for stamp in right_only) if shared else 0,
                "shared_candle_count": len(shared),
                "shared_timestamp_ratio": round(
                    len(shared) / len(set(left) | set(right)), 4
                ) if (set(left) | set(right)) else 0.0,
                "shared_window_start_utc": (
                    datetime.fromtimestamp(shared[0] / 1000, timezone.utc).isoformat()
                    if shared else None
                ),
                "shared_window_end_utc": (
                    datetime.fromtimestamp(shared[-1] / 1000, timezone.utc).isoformat()
                    if shared else None
                ),
                "price_discrepancy_bps_max": round(max_price, 4) if max_price is not None and math.isfinite(max_price) else max_price,
                "price_ratio_summary": price_ratio_summary,
                "largest_price_discrepancies": largest_price_discrepancies,
                "volume_discrepancy_bps_max": round(max_volume, 4) if max_volume is not None and math.isfinite(max_volume) else max_volume,
                "zero_positive_volume_mismatch_count": zero_positive_volume_mismatch_count if volume_units_comparable else None,
                "largest_volume_discrepancies": largest_volume_discrepancies,
                "price_within_tolerance": max_price is not None and max_price <= price_tolerance_bps,
                "volume_within_tolerance": volume_units_comparable and max_volume is not None and max_volume <= volume_tolerance_bps,
                "volume_comparability": volume_comparability_status,
            })

    has_alignment = all(item["shared_candle_count"] > 0 for item in pairwise)
    within_tolerance = has_alignment and all(
        item["price_within_tolerance"] and item["volume_within_tolerance"] for item in pairwise
    )
    return {
        "mode": "read_only",
        "interval": interval,
        "provider_count": len(normalized),
        "market_identity": (
            {"base_asset": next(iter(normalized_market_identities.values()))[0],
             "quote_asset": next(iter(normalized_market_identities.values()))[1],
             "verified_across_inputs": True}
            if normalized_market_identities is not None else
            {"verified_across_inputs": False, "note": "Market identity was not supplied to this offline comparison."}
        ),
        "providers": providers,
        "timeline_gaps": timeline_gaps,
        "timeline_gap_count": len(timeline_gaps),
        "provider_missing_interval_count": provider_missing_interval_count,
        "pairwise_comparisons": pairwise,
        "price_tolerance_bps": float(price_tolerance_bps),
        "volume_tolerance_bps": float(volume_tolerance_bps),
        "volume_units_by_provider": normalized_volume_units,
        "volume_units_comparable": volume_units_comparable,
        "caller_declared_volume_units_match": caller_declared_units_match,
        "volume_comparability_status": volume_comparability_status,
        "volume_semantics_by_provider": normalized_volume_semantics,
        "consistency_status": (
            "market_identity_unverified" if normalized_market_identities is None else
            "volume_units_unverified" if not volume_units_comparable and has_alignment and all(item["price_within_tolerance"] for item in pairwise) else
            "consistent_within_configured_tolerances"
            if within_tolerance and not timeline_gaps and provider_missing_interval_count == 0 else
            "insufficient_timestamp_overlap" if not has_alignment else
            "discrepancies_or_gaps_detected"
        ),
        "comparability_requirements": {
            "market_identity_verified": normalized_market_identities is not None,
            "exact_timestamp_overlap_required": True,
            "all_provider_pairs_have_overlap": has_alignment,
            "coverage_must_be_reviewed": True,
            "price_and_volume_tolerances_are_diagnostic_only": True,
            "volume_unit_identity_verified": volume_units_comparable,
            "caller_declared_units_are_not_independent_evidence": True,
            "source_verified_volume_semantics_required": True,
        },
        "limitations": [
            "Market identity must be supplied explicitly to obtain a consistency result; absent identity is reported as unverified.",
            "Provider snapshots are compared at exact candle-open timestamps; differing candle boundaries are not interpolated.",
            "A tolerance result is a diagnostic, not proof that either provider is correct or independently audited.",
            "Volume deltas are withheld unless every provider has matching source-verified volume semantics and asset identity; caller-declared unit labels alone are insufficient.",
            "Large price discrepancies include the five largest exact-overlap OHLC observations and signed left/right price-ratio summaries; no undocumented outlier threshold or trusted-provider ranking is applied.",
            "Caller-declared matching volume labels are reported as declarations only and never authorize volume deltas. Cross-provider volume observations require an exact CIN-registry source-verified semantics match, including basis and market asset identity.",
            "Known provider names are checked against their supported candle boundaries; generic provider labels receive timeframe-duration validation without an assumed weekly anchor.",
        ],
    }



COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
COINBASE_GRANULARITY = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}


def _coinbase_request_json(url: str) -> Any:
    """Classify invalid successful Coinbase response bodies as malformed, not outages."""
    try:
        return _request_json(url)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        raise _MalformedProviderResponse("Coinbase returned an invalid successful response body") from None


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
    # Anchor the requested history window to the provider's UTC granularity.
    # This prevents fractional first/last buckets and keeps adjacent page
    # boundaries on exact candle-open timestamps.
    latest_open = (now // duration) * duration
    start = latest_open - limit * duration
    rows_by_time: dict[int, list[Any]] = {}
    # Coinbase caps each response at 300 candles; fetch non-overlapping,
    # granularity-aligned windows. Timestamp-keyed collection deduplicates any
    # boundary row repeated by the upstream API.
    cursor = start
    while cursor < now:
        chunk_end = min(now, cursor + 300 * duration)
        query = urllib.parse.urlencode({
            "granularity": duration,
            "start": datetime.fromtimestamp(cursor, timezone.utc).isoformat(),
            "end": datetime.fromtimestamp(chunk_end, timezone.utc).isoformat(),
        })
        url = COINBASE_CANDLES_URL.format(product_id=urllib.parse.quote(product_id, safe="")) + "?" + query
        payload = _coinbase_request_json(url)
        if not isinstance(payload, list):
            raise _MalformedProviderResponse("Coinbase response was not a list")
        if len(payload) > 300:
            raise _MalformedProviderResponse("Coinbase response exceeded the 300-candle per-request limit")
        for row in payload:
            if not isinstance(row, list) or len(row) < 6:
                raise _MalformedProviderResponse("Coinbase returned a malformed candle row")
            try:
                # Malformed timestamps must not disappear from the returned snapshot.
                if isinstance(row[0], bool):
                    raise _MalformedProviderResponse("Coinbase returned a boolean candle timestamp")
                timestamp_seconds = float(row[0])
                if (
                    not math.isfinite(timestamp_seconds)
                    or not timestamp_seconds.is_integer()
                    or timestamp_seconds < 0
                    or timestamp_seconds * 1000 > MAX_TIMESTAMP_MS
                ):
                    raise _MalformedProviderResponse("Coinbase returned an invalid candle timestamp")
                timestamp_seconds_int = int(timestamp_seconds)
            except _MalformedProviderResponse:
                raise
            except (TypeError, ValueError, OverflowError):
                raise _MalformedProviderResponse("Coinbase returned a malformed candle row") from None
            # Coinbase may include the single candle immediately preceding
            # the page start. A response containing older rows or rows beyond
            # this page's end is not trusted as belonging to the requested page.
            page_floor = max(start - duration, cursor - duration)
            if timestamp_seconds_int < page_floor or timestamp_seconds_int > chunk_end:
                raise _MalformedProviderResponse(
                    "Coinbase returned a candle outside the requested pagination page"
                )
            # Keep only opens inside CIN's overall requested UTC history window.
            if start <= timestamp_seconds_int <= latest_open:
                previous_row = rows_by_time.get(timestamp_seconds_int)
                if previous_row is not None and previous_row != row:
                    raise _MalformedProviderResponse(
                        "Coinbase returned conflicting candle rows for the same open timestamp"
                    )
                rows_by_time[timestamp_seconds_int] = row
        cursor = chunk_end
    candles = []
    # Validate every collected row before selecting the requested latest
    # window. Otherwise an invalid newest row can consume one of the limit
    # slots and unnecessarily discard an older valid candle.
    for row in sorted(rows_by_time.values(), key=lambda item: int(item[0])):
        try:
            start_ms = int(row[0]) * 1000
            duration_ms = duration * 1000
            # Coinbase rows are [time, low, high, open, close, volume].
            candle = {
                "open_time": start_ms, "open": float(row[3]), "high": float(row[2]),
                "low": float(row[1]), "close": float(row[4]), "volume": float(row[5]),
                "close_time": start_ms + duration_ms - 1,
            }
            if not _is_valid_candle(candle):
                raise _MalformedProviderResponse("Coinbase returned invalid OHLCV values")
            candles.append(candle)
        except _MalformedProviderResponse:
            raise
        except (TypeError, ValueError, OverflowError):
            raise _MalformedProviderResponse("Coinbase returned a malformed candle row") from None
    if not candles:
        raise _MalformedProviderResponse("Coinbase returned no valid candles")
    return candles[-limit:]


def _fetch_klines(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    """Compatibility wrapper retained for existing tests and integrations."""
    return _fetch_binance(symbol, interval, limit)


def _validate_provider_snapshot_provenance(
    rows: list[dict[str, Any]], provider: str, source: str, endpoint: str,
    fallback_reason: str | None,
) -> None:
    """Fail closed unless every returned candle carries one coherent provider identity."""
    expected = {
        "binance": ("Binance public market-data API", BINANCE_KLINES_URL),
        "kraken": ("Kraken public OHLC API", KRAKEN_OHLC_URL),
        "coinbase": ("Coinbase Exchange public candles API", COINBASE_CANDLES_URL),
    }
    if provider not in expected or not isinstance(rows, list) or not rows:
        raise ValueError("Provider snapshot provenance is incomplete")
    expected_source, expected_endpoint = expected[provider]
    if endpoint != expected_endpoint or not isinstance(source, str) or not source.startswith(expected_source):
        raise ValueError("Provider snapshot source does not match its selected provider")
    if fallback_reason is None:
        if source != expected_source or provider != "binance":
            raise ValueError("Unexpected provider fallback metadata")
    elif fallback_reason not in {"Binance HTTP 451", "Binance transport failure"} or fallback_reason not in source:
        raise ValueError("Provider fallback reason does not match its source label")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Provider snapshot contains a non-object candle")
        if (
            row.get("_provider") != provider
            or row.get("_source") != source
            or row.get("_source_endpoint") != endpoint
        ):
            raise ValueError("Provider snapshot contains mixed or mismatched provenance metadata")


async def _load(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    """Load one provider snapshot; only transport failures and HTTP 451 fail over."""
    fallback_reason = None
    provider = "binance"
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
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        # A malformed or oversized successful response is not a transport outage:
        # fail closed and do not fan out to another provider.
        raise HTTPException(status_code=502, detail="Binance public market-data provider returned an invalid response.") from None

    if fallback_reason is not None:
        try:
            rows = await asyncio.to_thread(_fetch_kraken, symbol, interval, limit)
            provider = "kraken"
            source = f"Kraken public OHLC API (fallback after {fallback_reason})"
            endpoint = KRAKEN_OHLC_URL
        except _MalformedProviderResponse:
            raise HTTPException(status_code=502, detail="Kraken public market-data provider returned a malformed candle row.") from None
        except urllib.error.HTTPError as exc:
            if exc.code in (418, 429):
                raise HTTPException(status_code=503, detail="Kraken public market-data rate limit reached; retry later.") from None
            try:
                rows = await asyncio.to_thread(_fetch_coinbase, symbol, interval, limit)
                provider = "coinbase"
                source = f"Coinbase Exchange public candles API (fallback after {fallback_reason})"
                endpoint = COINBASE_CANDLES_URL
            except _MalformedProviderResponse:
                raise HTTPException(status_code=502, detail="Coinbase public market-data provider returned a malformed response.") from None
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as coinbase_exc:
                reason = "Kraken and Coinbase fallbacks unavailable or pair/timeframe unsupported"
                if isinstance(coinbase_exc, urllib.error.HTTPError):
                    reason += f" (Coinbase HTTP {coinbase_exc.code})"
                raise HTTPException(status_code=503, detail=reason + f"; {fallback_reason}.") from None
        except _MalformedProviderResponse:
            raise HTTPException(status_code=502, detail="Kraken public market-data provider returned a malformed candle row.") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            try:
                rows = await asyncio.to_thread(_fetch_coinbase, symbol, interval, limit)
                provider = "coinbase"
                source = f"Coinbase Exchange public candles API (fallback after {fallback_reason})"
                endpoint = COINBASE_CANDLES_URL
            except _MalformedProviderResponse:
                raise HTTPException(status_code=502, detail="Coinbase public market-data provider returned a malformed response.") from None
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as coinbase_exc:
                reason = "Kraken and Coinbase fallbacks unavailable or pair/timeframe unsupported"
                if isinstance(coinbase_exc, urllib.error.HTTPError):
                    reason += f" (Coinbase HTTP {coinbase_exc.code})"
                raise HTTPException(status_code=503, detail=reason + f"; {fallback_reason}.") from None

    try:
        rows = _normalize_candle_sequence(rows, interval, provider)
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="Public market-data provider returned an ambiguous candle sequence.") from None
    for row in rows:
        row["_source"] = source
        row["_source_endpoint"] = endpoint
        row["_provider"] = provider
    try:
        _validate_provider_snapshot_provenance(rows, provider, source, endpoint, fallback_reason)
    except (AttributeError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="Public market-data provider returned inconsistent source provenance.") from None
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
    try:
        freshness = _freshness_metadata(rows, interval, now_ms)
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="Public market-data provider returned invalid candle freshness timestamps.") from None
    try:
        timeline_integrity = _timeline_integrity_metadata(rows, interval)
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="Public market-data provider returned inconsistent candle timeline metadata.") from None
    try:
        data_quality = _provider_data_quality_metadata(rows, interval, now_ms)
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="Public market-data provider returned invalid OHLCV data quality metadata.") from None
    source = rows[0].get("_source", "Binance public market-data API")
    endpoint = rows[0].get("_source_endpoint", BINANCE_KLINES_URL)
    provider = rows[0].get("_provider", "unknown")
    # Kraken and Coinbase document that historical candle intervals without
    # trades may be omitted. Keep gaps visible without implying feed loss.
    no_trade_gap_provider = provider in {"kraken", "coinbase"}
    timeline_integrity["provider"] = provider
    timeline_integrity["gap_interpretation"] = (
        "missing_intervals_may_indicate_no_trades"
        if no_trade_gap_provider and timeline_integrity["has_gaps"]
        else "cause_not_inferred_from_candle_rows"
    )
    timeline_integrity["interpretation_note"] = (
        f"{provider.title()} may omit intervals with no trades; a reported gap is not proof of feed loss."
        if no_trade_gap_provider and timeline_integrity["has_gaps"]
        else "A timestamp gap identifies an absent interval only; its cause is not established by this snapshot."
    )
    return {
        "service": "cin", "mode": "read_only", "source": source, "source_endpoint": endpoint,
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "symbol": normalized,
        "timeframe": interval, "count": len(rows),
        "volume_semantics": _provider_volume_semantics(provider),
        "coverage": _coverage_metadata(rows, limit),
        "historical_window_integrity": _historical_window_integrity_metadata(
            rows, interval, limit, provider, now_ms
        ),
        **freshness,
        "data_quality": data_quality,
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
    try:
        freshness = _freshness_metadata(rows, interval, now_ms)
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="Public market-data provider returned invalid candle freshness timestamps.") from None
    source = rows[0].get("_source", "Binance public market-data API")
    endpoint = rows[0].get("_source_endpoint", BINANCE_KLINES_URL)
    try:
        analysis = analyze_ohlc([{key: row[key] for key in ("open", "high", "low", "close")} for row in closed_rows])
        timeline_integrity = _timeline_integrity_metadata(rows, interval)
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="Fetched public candles failed technical-analysis integrity validation.") from None
    analysis["input"].update({
        "symbol": normalized, "timeframe": interval, "source": source, "source_endpoint": endpoint,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "requested_candle_count": limit,
        "returned_candle_count": len(rows),
        "candle_count_shortfall": max(0, limit - len(rows)),
        "coverage_status": "complete" if len(rows) >= limit else "partial",
        "analysis_candle_count": len(closed_rows),
        "forming_candle_excluded_count": len(rows) - len(closed_rows),
        "candle_closure_policy": "technical analysis uses only candles whose close_time is earlier than retrieval time",
        "first_candle_open_time_utc": datetime.fromtimestamp(closed_rows[0]["open_time"] / 1000, timezone.utc).isoformat(),
        "last_candle_close_time_utc": datetime.fromtimestamp(closed_rows[-1]["close_time"] / 1000, timezone.utc).isoformat(),
        "volume_included_in_source_but_not_used_in_indicators": True,
        **freshness,
        "timeline_integrity": timeline_integrity,
    })
    analysis["limitations"].extend([
        "Public exchange data is not independently audited by CIN.",
        "The market-candles endpoint labels forming candles; the technical-analysis endpoint excludes them.",
        "Technical outputs and ATR scenarios are descriptive research, not investment advice or trade instructions.",
    ])
    return analysis
