"""Read-only Binance USDⓈ-M futures derivatives snapshot; no trading operations."""
from __future__ import annotations

import json
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


def _get_json(path: str, params: dict[str, str]) -> Any:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{_BASE}{path}?{query}",
        headers={"accept": "application/json", "user-agent": _USER_AGENT},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
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


def _validate_payloads(open_interest: Any, premium: Any, history: Any, symbol: str) -> None:
    if not isinstance(open_interest, dict) or open_interest.get("symbol") != symbol:
        raise ValueError("Unexpected open-interest provider payload")
    if not isinstance(premium, dict) or premium.get("symbol") != symbol:
        raise ValueError("Unexpected premium-index provider payload")
    if not isinstance(history, list) or any(not isinstance(row, dict) for row in history):
        raise ValueError("Unexpected open-interest history provider payload")


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

    oi_contracts = _finite_number(open_interest.get("openInterest"))
    funding_rate = _finite_number(premium.get("lastFundingRate"))
    mark_price = _finite_number(premium.get("markPrice"))
    index_price = _finite_number(premium.get("indexPrice"))
    if oi_contracts is None or oi_contracts < 0 or funding_rate is None:
        raise ValueError("Provider returned missing or invalid open-interest/funding values")
    if mark_price is None or mark_price <= 0 or index_price is None or index_price <= 0:
        raise ValueError("Provider returned missing or invalid mark/index price")

    bids = [(_finite_number(level[0]), _finite_number(level[1])) for level in depth["bids"] if isinstance(level, (list, tuple)) and len(level) >= 2]
    asks = [(_finite_number(level[0]), _finite_number(level[1])) for level in depth["asks"] if isinstance(level, (list, tuple)) and len(level) >= 2]
    bids = [(price, qty) for price, qty in bids if price is not None and price > 0 and qty is not None and qty > 0]
    asks = [(price, qty) for price, qty in asks if price is not None and price > 0 and qty is not None and qty > 0]
    if not bids or not asks:
        raise ValueError("Provider returned no valid bid/ask levels")
    best_bid = max(price for price, _ in bids)
    best_ask = min(price for price, _ in asks)
    if best_ask < best_bid:
        raise ValueError("Order-book best ask is below best bid")
    midpoint = (best_bid + best_ask) / 2
    bid_notional = sum(price * qty for price, qty in bids)
    ask_notional = sum(price * qty for price, qty in asks)
    total_notional = bid_notional + ask_notional
    depth_imbalance = (bid_notional - ask_notional) / total_notional if total_notional > 0 else None

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
        change_pct = round((latest_oi_value - previous_oi_value) / previous_oi_value * 100, 6)
    retrieved_at = datetime.now(timezone.utc).isoformat()

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
        "order_book": {
            "source": "Binance USDⓈ-M Futures public depth endpoint",
            "retrieved_at": retrieved_at,
            "bid_levels_used": len(bids),
            "ask_levels_used": len(asks),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": round(best_ask - best_bid, 10),
            "spread_percent": round((best_ask - best_bid) / midpoint * 100, 8) if midpoint > 0 else None,
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
            "funding_rate_percent_per_interval": round(funding_rate * 100, 8),
            "funding_rate_unit_note": "Percentage per current funding interval, not an annualized rate",
            "mark_price": mark_price,
            "index_price": index_price,
        },
        "liquidations": {
            "status": "not_available",
            "reason": "A reliable liquidation window requires continuous event ingestion and timestamped aggregation; no liquidation total is inferred from this snapshot.",
        },
        "data_quality": {
            "cache_used": False,
            "open_interest_change_window": "Latest two provider 4-hour aggregates; null when insufficient valid history exists",
            "limitations": [
                "Single-exchange derivatives data; it does not represent the entire market.",
                "Provider timestamps are retained separately from CIN retrieval time.",
                "Open-interest history is limited by the upstream provider's retention and availability.",
                "This endpoint is informational only and does not place, modify, or cancel orders.",
            ],
        },
    }


@router.get("/derivatives/market-snapshot")
async def derivatives_market_snapshot(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20, pattern=r"^[A-Za-z0-9]+\z"),
):
    """Return a read-only public derivatives snapshot; no account or trading endpoints are used."""
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
