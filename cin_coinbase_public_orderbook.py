"""Bounded read-only Coinbase Advanced public product-book adapter.

This module uses Coinbase's explicitly public market endpoint and never loads
API credentials, signs requests, routes orders, or controls accounts. It is
not registered in CIN's production service.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from cin_shortlist_orderbook_liquidity import assess_order_book

PUBLIC_BOOK_URL = "https://api.coinbase.com/api/v3/brokerage/market/product_book"
MAX_RESPONSE_BYTES = 512_000
MAX_LEVELS = 50


class PublicBookError(ValueError):
    """Public Coinbase book failed a bounded transport or contract check."""


def _pair(product_id: str) -> str:
    if not isinstance(product_id, str) or re.fullmatch(r"[A-Z0-9]{2,20}-[A-Z0-9]{2,12}", product_id) is None:
        raise ValueError("invalid Coinbase product ID")
    return product_id


def _levels(rows: Any, side: str) -> list[list[str]]:
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_LEVELS:
        raise PublicBookError(f"{side}: expected 1..50 levels")
    result = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"price", "size"}:
            raise PublicBookError(f"{side}[{i}]: invalid level shape")
        if not isinstance(row["price"], str) or not isinstance(row["size"], str):
            raise PublicBookError(f"{side}[{i}]: decimal fields must be strings")
        result.append([row["price"], row["size"]])
    return result


def fetch_coinbase_public_book(
    product_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read public L2 market data; reject ambiguous identity or redirected hosts.

    The result includes provider-route provenance, not independent evidence
    that exchange liquidity is executable or that all levels were available.
    """
    product_id = _pair(product_id)
    params = urllib.parse.urlencode({"product_id": product_id, "limit": MAX_LEVELS})
    url = f"{PUBLIC_BOOK_URL}?{params}"
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "CIN-ReadOnly-Research/0.1"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            if response.status != 200:
                raise PublicBookError("Coinbase public book returned non-success status")
            # Reject cross-host/path redirects; never quietly trust an unrelated origin.
            if response.geturl() != url:
                raise PublicBookError("Coinbase public book redirected unexpectedly")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, TimeoutError) as exc:
        raise PublicBookError("Coinbase public book transport failed") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise PublicBookError("Coinbase public book response too large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise PublicBookError("Coinbase public book invalid JSON") from exc
    if not isinstance(payload, dict) or "pricebook" not in payload:
        raise PublicBookError("Coinbase public book malformed envelope")
    # Coinbase documents optional top-level quote metrics in addition to pricebook.
    # They are not substitutes for independently checking bid/ask levels.
    optional = {"last", "mid_market", "spread_bps", "spread_absolute"}
    if set(payload) - ({"pricebook"} | optional):
        raise PublicBookError("Coinbase public book unexpected envelope fields")
    for name in optional & set(payload):
        if not isinstance(payload[name], str) or not payload[name] or len(payload[name]) > 128:
            raise PublicBookError(f"Coinbase public book invalid {name} field")
    pricebook = payload["pricebook"]
    if not isinstance(pricebook, dict) or set(pricebook) != {"product_id", "bids", "asks", "time"}:
        raise PublicBookError("Coinbase pricebook malformed fields")
    if pricebook["product_id"] != product_id:
        raise PublicBookError("Coinbase book product identity mismatch")
    snapshot = {
        "symbol": product_id,
        "source": "coinbase-advanced-public-market-product-book",
        "observed_at": pricebook["time"],
        "bids": _levels(pricebook["bids"], "bids"),
        "asks": _levels(pricebook["asks"], "asks"),
    }
    try:
        diagnostics = assess_order_book(snapshot, now=now)
    except (ValueError, OverflowError) as exc:
        raise PublicBookError("Coinbase public book invalid L2 snapshot") from exc
    return {
        "provider": "coinbase",
        "product_id": product_id,
        "endpoint": PUBLIC_BOOK_URL,
        "request_method": "GET",
        "authenticated": False,
        "provenance": "fixed_https_public_endpoint",
        "snapshot": snapshot,
        "diagnostics": diagnostics,
        "execution_enabled": False,
    }
