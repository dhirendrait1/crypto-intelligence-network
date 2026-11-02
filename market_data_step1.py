"""CIN Step 1: read-only Coinbase Exchange public market data.

Only explicitly mapped USD-quoted Coinbase products are supported. Market
capitalization is not supplied by this exchange endpoint and remains null.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
import math
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["market-data"])

COINBASE_API = "https://api.exchange.coinbase.com"
COINBASE_ASSETS = {
    "bitcoin": ("BTC", "Bitcoin"),
    "ethereum": ("ETH", "Ethereum"),
}
MARKET_DATA_MAX_AGE = timedelta(minutes=15)
FUTURE_TIMESTAMP_TOLERANCE = timedelta(minutes=5)
MAX_PROVIDER_RESPONSE_BYTES = 2_000_000


def _finite_number(value: Any, *, minimum: float | None = None) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        numeric_value = float(value)
    except (OverflowError, TypeError, ValueError):
        return False
    if not math.isfinite(numeric_value):
        return False
    return minimum is None or numeric_value >= minimum



def _provider_number(value: Any, *, minimum: float | None = None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        return None
    return number

def _timestamp_status(value: Any) -> tuple[str, int | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return "unknown", None, "missing_or_invalid_last_updated"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return "unknown", None, "timezone_missing_from_last_updated"
        parsed = parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError, OSError):
        return "unknown", None, "invalid_last_updated_timestamp"
    now = datetime.now(timezone.utc)
    if parsed > now + FUTURE_TIMESTAMP_TOLERANCE:
        return "unknown", None, "future_last_updated_timestamp"
    age = max(0, int((now - parsed).total_seconds()))
    return ("fresh" if age <= MARKET_DATA_MAX_AGE.total_seconds() else "stale"), age, None


def _coinbase_json(path: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{COINBASE_API}{path}",
        headers={"accept": "application/json", "user-agent": "CIN-Research-API/0.1.0"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        if response.status != 200:
            raise ValueError(f"Coinbase returned unexpected HTTP status {response.status}")
        raw = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
    if len(raw) > MAX_PROVIDER_RESPONSE_BYTES:
        raise ValueError("Coinbase response exceeded the configured size limit")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Coinbase response was not an object")
    return payload




def _fetch_market_data(ids: list[str], vs_currency: str) -> list[dict[str, Any]]:
    if vs_currency.lower() != "usd":
        raise ValueError("Coinbase market-data route supports USD quotes only")
    normalized = []
    for coin_id in ids:
        asset = COINBASE_ASSETS.get(coin_id)
        if asset is None:
            continue
        symbol, name = asset
        product_id = f"{symbol}-USD"
        stats = _coinbase_json(f"/products/{product_id}/stats")
        ticker = _coinbase_json(f"/products/{product_id}/ticker")
        price = stats.get("last")
        volume = stats.get("volume")
        open_price = stats.get("open")
        price_value = _provider_number(price, minimum=0)
        if price_value is None:
            continue
        warnings = []
        volume_value = _provider_number(volume, minimum=0)
        if volume_value is None:
            warnings.append("invalid_total_volume_omitted")
        change = None
        open_value = _provider_number(open_price, minimum=0)
        if open_value is not None and open_value > 0:
            calculated_change = (price_value / open_value - 1.0) * 100.0
            if math.isfinite(calculated_change):
                change = calculated_change
            else:
                warnings.append("invalid_price_change_percentage_omitted")
        else:
            warnings.append("price_change_unavailable")
        last_updated = ticker.get("time")
        freshness_status, freshness_age_seconds, timestamp_warning = _timestamp_status(last_updated)
        if timestamp_warning:
            warnings.append(timestamp_warning)
        if freshness_status == "stale":
            warnings.append("market_data_older_than_15_minutes")
        if price_value == 0:
            warnings.append("zero_price_not_suitable_for_analysis")
        if volume_value is None:
            warnings.append("volume_24h_unavailable")
        elif volume_value == 0:
            warnings.append("zero_volume_not_liquidity_evidence")
        warnings.append("market_cap_unavailable_from_coinbase_exchange")
        normalized.append({
            "id": coin_id, "symbol": symbol, "name": name, "currency": "USD",
            "price": price_value, "market_cap": None, "market_cap_status": "unavailable",
            "total_volume_24h": volume_value,
            "total_volume_24h_unit": symbol,
            "volume_24h_currency": symbol,
            "volume_24h_status": "missing" if volume_value is None else ("zero" if volume_value == 0 else "reported_positive"),
            "price_change_percentage_24h": change, "last_updated": last_updated,
            "freshness_status": freshness_status, "freshness_age_seconds": freshness_age_seconds,
            "analysis_eligible": freshness_status == "fresh" and price_value > 0,
            "data_quality_warnings": warnings, "product_id": product_id,
        })
    return normalized


@router.get("/market-data")
async def get_public_market_data(
    coins: str = Query(default="bitcoin,ethereum", description="Comma-separated supported CIN asset IDs (bitcoin, ethereum)"),
    vs_currency: str = Query(default="usd", min_length=2, max_length=10),
) -> dict[str, Any]:
    """Fetch normalized public market data. Read-only; never places trades."""
    ids = list(dict.fromkeys(item.strip().lower() for item in coins.split(",") if item.strip()))
    if not ids or len(ids) > 10:
        raise HTTPException(status_code=400, detail="Provide between 1 and 10 asset IDs.")
    if any(not item.replace("-", "").isalnum() for item in ids):
        raise HTTPException(status_code=400, detail="Asset IDs may contain letters, numbers, and hyphens only.")
    currency = vs_currency.strip().lower()
    if not 2 <= len(currency) <= 10 or not currency.isascii() or not currency.isalpha():
        raise HTTPException(
            status_code=400,
            detail="Currency must be a 2-10 character ASCII alphabetic code.",
        )

    if currency != "usd":
        raise HTTPException(status_code=400, detail="Coinbase market-data route supports USD quotes only.")

    try:
        rows = await asyncio.to_thread(_fetch_market_data, ids, currency)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise HTTPException(status_code=503, detail="Market-data provider rate limit reached; retry later.") from exc
        raise HTTPException(status_code=502, detail=f"Market-data provider returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError):
        raise HTTPException(status_code=503, detail="Market-data provider is temporarily unavailable.") from None
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="Market-data provider returned an invalid response.") from None
    except Exception:
        # Keep unexpected provider/parser failures inside CIN's stable public API contract.
        raise HTTPException(
            status_code=502,
            detail="Market-data provider returned an unexpected response.",
        ) from None

    if not rows:
        raise HTTPException(status_code=502, detail="No supported Coinbase USD market data was returned for the requested asset IDs.")

    returned_ids = {row["id"] for row in rows}
    missing_ids = [coin_id for coin_id in ids if coin_id not in returned_ids]
    return {
        "service": "cin",
        "source": "Coinbase Exchange public API",
        "mode": "read_only",
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "freshness_policy": "row is fresh when provider last_updated is no more than 15 minutes old; stale beyond 15 minutes; unknown when timestamp is missing or invalid",
        "currency": currency.upper(),
        "requested_count": len(ids),
        "count": len(rows),
        "partial_result": bool(missing_ids),
        "missing_coins": missing_ids,
        "provider_limitations": [
            "Coinbase Exchange does not provide market capitalization through these endpoints.",
            "Only explicitly mapped Coinbase USD products are supported.",
            "Coinbase 24-hour stats volume is denominated in the base asset, not USD quote turnover.",
        ],
        "data": rows,
    }
