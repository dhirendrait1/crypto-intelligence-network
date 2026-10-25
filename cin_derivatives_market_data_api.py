"""Read-only Binance USDⓈ-M futures derivatives snapshot; no trading operations."""
from __future__ import annotations

import json
import re
import math
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["derivatives-market-data"])
_BASE = "https://fapi.binance.com"
_USER_AGENT = "CIN-Research-API/0.4.0"
_MAX_PROVIDER_RESPONSE_BYTES = 1_000_000
_MAX_OPEN_INTEREST_HISTORY_ROWS = 2
_MAX_ORDER_BOOK_LEVELS_PER_SIDE = 20


def _get_json(path: str, params: dict[str, str]) -> Any:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{_BASE}{path}?{query}",
        headers={"accept": "application/json", "user-agent": _USER_AGENT},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(_MAX_PROVIDER_RESPONSE_BYTES + 1)
    if len(raw) > _MAX_PROVIDER_RESPONSE_BYTES:
        raise ValueError("Derivatives provider response exceeded the configured size limit")
    payload = json.loads(raw.decode("utf-8"))
    return payload


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _iso_from_ms(value: Any) -> str | None:
    timestamp = _finite_number(value)
    if timestamp is None or timestamp < 0:
        return None
    try:
        return datetime.fromtimestamp(timestamp / 1000, timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None



def _timestamp_quality(value: Any, now: datetime, stale_after_seconds: int, future_tolerance_seconds: int = 60) -> dict[str, Any]:
    if value is None:
        return {"timestamp": None, "age_seconds": None, "status": "unavailable"}
    timestamp = _finite_number(value)
    iso_timestamp = _iso_from_ms(value)
    if timestamp is None or iso_timestamp is None:
        return {"timestamp": None, "age_seconds": None, "status": "invalid"}
    age_seconds = (now - datetime.fromtimestamp(timestamp / 1000, timezone.utc)).total_seconds()
    if age_seconds < -future_tolerance_seconds:
        status = "future_dated"
    elif age_seconds > stale_after_seconds:
        status = "stale"
    else:
        status = "fresh"
    return {
        "timestamp": iso_timestamp,
        "age_seconds": round(age_seconds, 3),
        "status": status,
        "stale_after_seconds": stale_after_seconds,
        "future_tolerance_seconds": future_tolerance_seconds,
    }

def _validate_payloads(open_interest: Any, premium: Any, history: Any, symbol: str) -> None:
    if not isinstance(open_interest, dict) or open_interest.get("symbol") != symbol:
        raise ValueError("Unexpected open-interest provider payload")
    if not isinstance(premium, dict) or premium.get("symbol") != symbol:
        raise ValueError("Unexpected premium-index provider payload")
    if _iso_from_ms(open_interest.get("time")) is None:
        raise ValueError("Open-interest provider payload contained an invalid timestamp")
    if _iso_from_ms(premium.get("time")) is None:
        raise ValueError("Premium-index provider payload contained an invalid timestamp")
    if (
        not isinstance(history, list)
        or len(history) > _MAX_OPEN_INTEREST_HISTORY_ROWS
        or any(not isinstance(row, dict) for row in history)
    ):
        raise ValueError("Unexpected open-interest history provider payload")
    seen_history_timestamps: set[float] = set()
    for row in history:
        if row.get("symbol") != symbol:
            raise ValueError("Open-interest history symbol did not match the requested symbol")
        history_value = _finite_number(row.get("sumOpenInterestValue"))
        history_timestamp = _finite_number(row.get("timestamp"))
        if history_value is None or history_value < 0:
            raise ValueError("Open-interest history contained an invalid notional value")
        if history_timestamp is None or history_timestamp < 0 or _iso_from_ms(history_timestamp) is None:
            raise ValueError("Open-interest history contained an invalid timestamp")
        if history_timestamp in seen_history_timestamps:
            raise ValueError("Open-interest history contained duplicate timestamps")
        seen_history_timestamps.add(history_timestamp)


def _snapshot(symbol: str) -> dict[str, Any]:
    open_interest = _get_json("/fapi/v1/openInterest", {"symbol": symbol})
    premium = _get_json("/fapi/v1/premiumIndex", {"symbol": symbol})
    history = _get_json(
        "/futures/data/openInterestHist",
        {"symbol": symbol, "period": "4h", "limit": "2"},
    )
    depth = _get_json("/fapi/v1/depth", {"symbol": symbol, "limit": "20"})
    depth_retrieved_at = datetime.now(timezone.utc).isoformat()
    _validate_payloads(open_interest, premium, history, symbol)
    if not isinstance(depth, dict) or not isinstance(depth.get("bids"), list) or not isinstance(depth.get("asks"), list):
        raise ValueError("Unexpected order-book depth provider payload")
    if (
        len(depth["bids"]) > _MAX_ORDER_BOOK_LEVELS_PER_SIDE
        or len(depth["asks"]) > _MAX_ORDER_BOOK_LEVELS_PER_SIDE
    ):
        raise ValueError("Order-book depth exceeded the requested level limit")

    oi_contracts = _finite_number(open_interest.get("openInterest"))
    funding_rate = _finite_number(premium.get("lastFundingRate"))
    mark_price = _finite_number(premium.get("markPrice"))
    index_price = _finite_number(premium.get("indexPrice"))
    if oi_contracts is None or oi_contracts < 0 or funding_rate is None:
        raise ValueError("Provider returned missing or invalid open-interest/funding values")
    if mark_price is None or mark_price <= 0 or index_price is None or index_price <= 0:
        raise ValueError("Provider returned missing or invalid mark/index price")

    def parse_levels(levels: list[Any]) -> tuple[list[tuple[float, float]], int]:
        parsed: list[tuple[float, float]] = []
        rejected = 0
        for level in levels:
            if not isinstance(level, (list, tuple)) or len(level) < 2:
                rejected += 1
                continue
            price = _finite_number(level[0])
            quantity = _finite_number(level[1])
            if price is None or price <= 0 or quantity is None or quantity <= 0:
                rejected += 1
                continue
            parsed.append((price, quantity))
        return parsed, rejected

    bids, rejected_bid_levels = parse_levels(depth["bids"])
    asks, rejected_ask_levels = parse_levels(depth["asks"])
    if not bids or not asks:
        raise ValueError("Provider returned no valid bid/ask levels")
    best_bid = max(price for price, _ in bids)
    best_ask = min(price for price, _ in asks)
    if best_ask < best_bid:
        raise ValueError("Order-book best ask is below best bid")
    midpoint = best_bid / 2 + best_ask / 2
    bid_notional = sum(price * qty for price, qty in bids)
    ask_notional = sum(price * qty for price, qty in asks)
    total_notional = bid_notional + ask_notional
    if not all(math.isfinite(value) for value in (midpoint, bid_notional, ask_notional, total_notional)):
        raise ValueError("Order-book arithmetic exceeded finite numeric limits")
    if midpoint <= 0 or total_notional <= 0:
        raise ValueError("Order-book arithmetic produced a non-positive midpoint or notional")
    depth_imbalance = (bid_notional - ask_notional) / total_notional
    if not math.isfinite(depth_imbalance):
        raise ValueError("Order-book imbalance was not finite")

    history_rows = sorted(
        history,
        key=lambda row: _finite_number(row.get("timestamp")) or 0,
    )
    latest_history = history_rows[-1] if history_rows else None
    previous_history = history_rows[-2] if len(history_rows) >= 2 else None
    latest_oi_value = _finite_number(latest_history.get("sumOpenInterestValue")) if latest_history else None
    previous_oi_value = _finite_number(previous_history.get("sumOpenInterestValue")) if previous_history else None
    change_pct = None
    if previous_oi_value is not None and previous_oi_value > 0 and latest_oi_value is not None:
        change_pct = (latest_oi_value - previous_oi_value) / previous_oi_value * 100

    spread = best_ask - best_bid
    spread_percent = spread / midpoint * 100
    funding_rate_percent = funding_rate * 100
    derived_values = [spread, spread_percent, funding_rate_percent]
    if change_pct is not None:
        derived_values.append(change_pct)
    if not all(math.isfinite(value) for value in derived_values):
        raise ValueError("Derived derivatives metrics exceeded finite numeric limits")

    if change_pct is not None:
        change_pct = round(change_pct, 6)
    retrieved_at_dt = datetime.now(timezone.utc)
    retrieved_at = retrieved_at_dt.isoformat()
    timestamp_quality = {
        "open_interest": _timestamp_quality(open_interest.get("time"), retrieved_at_dt, 900),
        "mark_price_and_funding": _timestamp_quality(premium.get("time"), retrieved_at_dt, 900),
        "open_interest_history_latest": _timestamp_quality(
            latest_history.get("timestamp") if latest_history else None,
            retrieved_at_dt,
            28800,
        ),
    }
    freshness_warnings = [
        name for name, quality in timestamp_quality.items()
        if quality["status"] in ("stale", "future_dated", "invalid", "unavailable")
    ]

    return {
        "service": "cin",
        "endpoint": "/derivatives/market-snapshot",
        "mode": "read_only",
        "source": "Binance USDⓈ-M Futures public market-data API",
        "symbol": symbol,
        "retrieved_at": retrieved_at,
        "provider_timestamps": {
            "open_interest": _iso_from_ms(open_interest.get("time")),
            "mark_price_and_funding": _iso_from_ms(premium.get("time")),
            "open_interest_history_latest": _iso_from_ms(latest_history.get("timestamp")) if latest_history else None,
        },
        "timestamp_quality": timestamp_quality,
        "order_book": {
            "source": "Binance USDⓈ-M Futures public depth endpoint",
            "retrieved_at": depth_retrieved_at,
            "bid_levels_used": len(bids),
            "ask_levels_used": len(asks),
            "bid_levels_rejected": rejected_bid_levels,
            "ask_levels_rejected": rejected_ask_levels,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": round(spread, 10),
            "spread_percent": round(spread_percent, 8),
            "bid_notional_quote_approx": round(bid_notional, 4),
            "ask_notional_quote_approx": round(ask_notional, 4),
            "bid_ask_notional_imbalance": round(depth_imbalance, 8) if depth_imbalance is not None else None,
            "note": "Snapshot only; depth changes rapidly and excludes retail price-improvement orders not exposed by this endpoint.",
        },
        "data": {
            "open_interest_contracts": oi_contracts,
            "open_interest_value_quote_approx": latest_oi_value,
            "open_interest_value_change_4h_percent": change_pct,
            "funding_rate": funding_rate,
            "funding_rate_percent_per_interval": round(funding_rate_percent, 8),
            "funding_rate_unit_note": "Percentage per current funding interval, not an annualized rate",
            "mark_price": mark_price,
            "index_price": index_price,
        },
        "liquidations": {
            "status": "not_available",
            "reason": "A reliable liquidation window requires continuous event ingestion and timestamped aggregation; no liquidation total is inferred from this snapshot.",
        },
        "data_quality": {
            "freshness_status": "warning" if freshness_warnings else "ok",
            "analysis_eligibility": "not_recommended" if freshness_warnings else "eligible",
            "analysis_eligibility_reason": (
                "One or more provider timestamp checks are stale, future-dated, invalid, or unavailable; review timestamp_quality before relying on derived metrics."
                if freshness_warnings else None
            ),
            "freshness_warnings": freshness_warnings,
            "freshness_policy": {
                "open_interest_and_premium_index_stale_after_seconds": 900,
                "open_interest_history_stale_after_seconds": 28800,
                "future_timestamp_tolerance_seconds": 60,
            },
            "cache_used": False,
            "open_interest_change_window": "Latest two provider 4-hour aggregates; null when insufficient valid history exists",
            "limitations": [
                "Single-exchange derivatives data; it does not represent the entire market.",
                "Provider timestamps are retained separately from CIN retrieval time.",
                "Malformed or non-positive order-book levels are excluded and counted in the order_book rejected-level fields.",
                "Open-interest history is limited by the upstream provider's retention and availability.",
                "This endpoint is informational only and does not place, modify, or cancel orders.",
            ],
        },
    }


@router.get("/derivatives/market-snapshot")
async def derivatives_market_snapshot(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"),
):
    """Return a read-only public derivatives snapshot; no account or trading endpoints are used."""
    if re.fullmatch(r"[A-Za-z0-9]{5,20}", symbol) is None:
        raise HTTPException(status_code=400, detail={
            "message": "Symbol must be a 5–20 character alphanumeric trading pair.",
            "error": "invalid_symbol",
        })
    normalized = symbol.upper()
    try:
        import asyncio
        return await asyncio.to_thread(_snapshot, normalized)
    except urllib.error.HTTPError as exc:
        status = 503 if exc.code == 429 or exc.code >= 500 else 502
        raise HTTPException(status_code=status, detail={
            "message": "Derivatives provider returned an HTTP error.",
            "provider": "Binance USDⓈ-M Futures",
            "error": "http_error",
            "http_status": exc.code,
        }) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail={
            "message": "Derivatives provider could not be reached.",
            "provider": "Binance USDⓈ-M Futures",
            "error": "network_error",
        }) from exc
    except (
        ValueError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        RuntimeError,
        TypeError,
        KeyError,
        IndexError,
        OverflowError,
    ) as exc:
        raise HTTPException(status_code=502, detail={
            "message": "Derivatives provider response was invalid or incomplete.",
            "provider": "Binance USDⓈ-M Futures",
            "error": "invalid_response",
        }) from exc
    except Exception as exc:
        # Keep unforeseen provider/parser failures inside the controlled API contract.
        raise HTTPException(status_code=502, detail={
            "message": "Derivatives provider response was invalid or incomplete.",
            "provider": "Binance USDⓈ-M Futures",
            "error": "invalid_response",
        }) from exc
