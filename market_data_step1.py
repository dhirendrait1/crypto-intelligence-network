"""CIN Step 1: read-only public market data from CoinGecko.

No API key, wallet access, or trade execution is used.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["market-data"])

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"


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
        if not isinstance(price, (int, float)):
            continue
        normalized.append({
            "id": coin.get("id"),
            "symbol": str(coin.get("symbol", "")).upper(),
            "name": coin.get("name"),
            "currency": vs_currency.upper(),
            "price": price,
            "market_cap": coin.get("market_cap"),
            "total_volume_24h": coin.get("total_volume"),
            "price_change_percentage_24h": coin.get("price_change_percentage_24h"),
            "last_updated": coin.get("last_updated"),
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
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "currency": currency.upper(),
        "count": len(rows),
        "data": rows,
    }
