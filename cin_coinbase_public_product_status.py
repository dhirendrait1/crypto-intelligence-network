"""Bounded, read-only Coinbase public product-status evidence.

Evaluates market availability for research only. This is not an execution
permission check, and it does not authorize trading or score approval.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any

from cin_coinbase_public_orderbook import _pair, PublicBookError

PUBLIC_PRODUCT_PREFIX = "https://api.coinbase.com/api/v3/brokerage/market/products/"
MAX_PRODUCT_BYTES = 256_000


def fetch_coinbase_public_product_status(product_id: str) -> dict[str, Any]:
    """Fetch one product from fixed public Coinbase API, fail closed on ambiguity."""
    product_id = _pair(product_id)
    url = PUBLIC_PRODUCT_PREFIX + product_id
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "CIN-ReadOnly-Research/0.1"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            if response.status != 200:
                raise PublicBookError("Coinbase public product non-success status")
            if response.geturl() != url:
                raise PublicBookError("Coinbase public product unexpected redirect")
            raw = response.read(MAX_PRODUCT_BYTES + 1)
    except (OSError, TimeoutError) as exc:
        raise PublicBookError("Coinbase public product transport failed") from exc
    if len(raw) > MAX_PRODUCT_BYTES:
        raise PublicBookError("Coinbase public product response too large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise PublicBookError("Coinbase public product invalid JSON") from exc
    if not isinstance(payload, dict):
        raise PublicBookError("Coinbase public product expected an object")
    if payload.get("product_id") != product_id:
        raise PublicBookError("Coinbase public product identity mismatch")
    base, quote = product_id.split("-")
    for field, expected in (("base_currency_id", base), ("quote_currency_id", quote)):
        if payload.get(field) != expected:
            raise PublicBookError(f"Coinbase public product {field} mismatch")

    status = payload.get("status")
    kind = payload.get("product_type")
    if not isinstance(status, str) or len(status) > 40:
        raise PublicBookError("Coinbase public product invalid status")
    if not isinstance(kind, str) or len(kind) > 40:
        raise PublicBookError("Coinbase public product invalid type")
    flags = ("is_disabled", "trading_disabled", "view_only", "auction_mode")
    for field in flags:
        if type(payload.get(field)) is not bool:
            raise PublicBookError(f"Coinbase public product {field} must be a boolean")
    # Conservative research eligibility, NOT an assertion of actual tradability.
    available = (
        status.lower() == "online"
        and kind == "SPOT"
        and not any(payload[field] for field in flags)
    )
    return {
        "provider": "coinbase",
        "product_id": product_id,
        "endpoint": url,
        "request_method": "GET",
        "authenticated": False,
        "execution_enabled": False,
        "status": status,
        "product_type": kind,
        "flags": {key: payload[key] for key in flags},
        "market_available_for_research": available,
        "source_verification": "fixed_public_coinbase_https_route",
    }
