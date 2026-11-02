"""Map the existing Coinbase market response to provisional shortlist evidence."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

_PRODUCTS = {"bitcoin": ("BTC", "BTC-USD", "BTCUSD"), "ethereum": ("ETH", "ETH-USD", "ETHUSD")}


def coinbase_market_evidence(payload: Any, *, asset_id: str, market_id: str, now: datetime) -> dict[str, Any]:
    """Validate supplied Coinbase USD ticker output without quote substitution."""
    if asset_id not in _PRODUCTS or not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Unsupported asset or invalid clock")
    symbol, product, expected_market = _PRODUCTS[asset_id]
    if market_id != expected_market:
        raise ValueError("Coinbase USD price cannot represent the requested market")
    if not isinstance(payload, dict) or payload.get("source") != "Coinbase Exchange public API" or payload.get("currency") != "USD":
        raise ValueError("Unexpected market source or quote")
    rows = payload.get("data")
    if not isinstance(rows, list) or len(rows) > 10 or payload.get("count") != len(rows):
        raise ValueError("Invalid market response")
    matches = [row for row in rows if isinstance(row, dict) and row.get("id") == asset_id]
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous asset")
    row = matches[0]
    if row.get("symbol") != symbol or row.get("currency") != "USD" or row.get("product_id") != product:
        raise ValueError("Market identity mismatch")
    if row.get("freshness_status") != "fresh" or row.get("analysis_eligible") is not True:
        raise ValueError("Market price is not eligible")
    price = row.get("price")
    try:
        valid = not isinstance(price, bool) and isinstance(price, (int, float)) and math.isfinite(price) and price > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("Invalid market price")
    raw = row.get("last_updated")
    if not isinstance(raw, str) or len(raw) > 64:
        raise ValueError("Missing market timestamp")
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Naive market timestamp")
        stamp = stamp.astimezone(timezone.utc)
        current = now.astimezone(timezone.utc)
        if stamp > current or current - stamp > timedelta(minutes=15):
            raise ValueError("Market timestamp outside freshness window")
    except (ValueError, OverflowError) as exc:
        raise ValueError("Invalid or stale market timestamp") from exc
    return {
        "status": "available", "asset_id": asset_id, "market_id": expected_market,
        "price": price, "source": "Coinbase Exchange public API",
        "source_url": "https://api.exchange.coinbase.com/products/" + product + "/ticker",
        "observed_at": stamp.isoformat(), "quote_currency": "USD", "product_id": product,
        "limitations": [
            "Coinbase USD and USDT markets are not interchangeable.",
            "Source authenticity is not independently verified by this adapter.",
            "24-hour statistics are retrieved separately and are not an atomic snapshot.",
        ],
    }

