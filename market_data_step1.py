"""CIN Step 1: read-only public market data from CoinGecko.

No API key, wallet access, or trade execution is used.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
import math
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["market-data"])

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
MARKET_DATA_MAX_AGE = timedelta(minutes=15)
FUTURE_TIMESTAMP_TOLERANCE = timedelta(minutes=5)


def _finite_number(value: Any, *, minimum: float | None = None) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if not math.isfinite(value):
        return False
    return minimum is None or value >= minimum


def _timestamp_status(value: Any) -> tuple[str, int | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return "unknown", None, "missing_or_invalid_last_updated"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "unknown", None, "invalid_last_updated_timestamp"
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return "unknown", None, "timezone_missing_from_last_updated"
    now = datetime.now(timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    if parsed > now + FUTURE_TIMESTAMP_TOLERANCE:
        return "unknown", None, "future_last_updated_timestamp"
    age = max(0, int((now - parsed).total_seconds()))
    return ("fresh" if age <= MARKET_DATA_MAX_AGE.total_seconds() else "stale"), age, None


def _fetch_market_data(ids: list[str], vs_currency: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({
        "vs_currency": vs_currency,
        "ids": ",".join(ids),
        "price_change_percentage": "24h",
    })
    request = urllib.request.Request(
        f"{COINGECKO_URL}?{params}",
        headers={
            "accept": "application/json",
            "user-agent": "CIN-Research-API/0.1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        if response.status != 200:
            raise RuntimeError(f"Provider returned HTTP {response.status}")
        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, list):
        raise ValueError("Provider response was not a list")

    normalized = []
    for coin in payload:
        if not isinstance(coin, dict):
            continue
        price = coin.get("current_price")
        if not _finite_number(price, minimum=0):
            continue
        warnings = []
        market_cap = coin.get("market_cap")
        if market_cap is not None and not _finite_number(market_cap, minimum=0):
            market_cap = None
            warnings.append("invalid_market_cap_omitted")
        volume = coin.get("total_volume")
        if volume is not None and not _finite_number(volume, minimum=0):
            volume = None
            warnings.append("invalid_total_volume_omitted")
        change = coin.get("price_change_percentage_24h")
        if change is not None and not _finite_number(change):
            change = None
            warnings.append("invalid_price_change_percentage_omitted")
        last_updated = coin.get("last_updated")
        freshness_status, freshness_age_seconds, timestamp_warning = _timestamp_status(last_updated)
        if timestamp_warning:
            warnings.append(timestamp_warning)
        if freshness_status == "stale":
            warnings.append("market_data_older_than_15_minutes")
        normalized.append({
            "id": coin.get("id"),
            "symbol": str(coin.get("symbol", "")).upper(),
            "name": coin.get("name"),
            "currency": vs_currency.upper(),
            "price": price,
            "market_cap": market_cap,
            "total_volume_24h": volume,
            "price_change_percentage_24h": change,
            "last_updated": last_updated,
            "freshness_status": freshness_status,
            "freshness_age_seconds": freshness_age_seconds,
            "data_quality_warnings": warnings,
        })
    return normalized


@router.get("/market-data")
async def get_public_market_data(
    coins: str = Query(default="bitcoin,ethereum", description="Comma-separated CoinGecko coin IDs"),
    vs_currency: str = Query(default="usd", min_length=2, max_length=10),
) -> dict[str, Any]:
    """Fetch normalized public market data. Read-only; never places trades."""
    ids = [item.strip().lower() for item in coins.split(",") if item.strip()]
    if not ids or len(ids) > 10:
        raise HTTPException(status_code=400, detail="Provide between 1 and 10 coin IDs.")
    if any(not item.replace("-", "").isalnum() for item in ids):
        raise HTTPException(status_code=400, detail="Coin IDs may contain letters, numbers, and hyphens only.")
    currency = vs_currency.strip().lower()
    if not currency.isalpha():
        raise HTTPException(status_code=400, detail="Currency must contain letters only.")

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

    if not rows:
        raise HTTPException(status_code=502, detail="No valid market data was returned for the requested coin IDs.")

    return {
        "service": "cin",
        "source": "CoinGecko public API",
        "mode": "read_only",
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "freshness_policy": "row is fresh when provider last_updated is no more than 15 minutes old; stale beyond 15 minutes; unknown when timestamp is missing or invalid",
        "currency": currency.upper(),
        "count": len(rows),
        "data": rows,
    }
