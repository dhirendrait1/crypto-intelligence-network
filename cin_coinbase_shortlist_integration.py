"""Opt-in Coinbase public-book to CIN shortlist eligibility integration.

One synchronous public GET via the existing bounded adapter, followed by
fail-closed evidence reconciliation. Nothing here places or routes orders.
The external market row remains caller supplied and is not authenticated.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from cin_coinbase_public_orderbook import PUBLIC_BOOK_URL, PublicBookError, fetch_coinbase_public_book
from cin_shortlist_liquidity_reconciliation import reconcile_liquidity
from cin_shortlist_market_snapshot import assess_market_snapshot


class ShortlistProviderIntegrityError(ValueError):
    """Market/source identity or public-provider integrity check failed."""


def evaluate_coinbase_liquidity(
    market_row: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_spread_bps: Any = "30",
    min_depth_quote_each_side: Any = "10000",
) -> dict[str, Any]:
    """Fetch public Coinbase L2 once, verify provenance, and reconcile.

    A fixed-HTTPS Coinbase request is a known acquisition route, not an
    independent verification of the other supplied market row or all market
    status fields. Positive shortlist liquidity remains unknown.
    """
    market = assess_market_snapshot(market_row, now=now)
    symbol, quote = market["symbol"], market["currency"]
    if not symbol.isascii() or not quote.isascii():
        raise ValueError("unsupported market pair characters")
    product_id = f"{symbol}-{quote}"
    if len(product_id) > 33:
        raise ValueError("market pair too long")
    # Validate before any request. Matching must never silently change quote currency.
    from cin_coinbase_public_orderbook import _pair
    _pair(product_id)
    book = fetch_coinbase_public_book(product_id, now=now)
    if (not isinstance(book, Mapping)
            or book.get("provider") != "coinbase"
            or book.get("product_id") != product_id
            or book.get("endpoint") != PUBLIC_BOOK_URL
            or book.get("request_method") != "GET"
            or book.get("authenticated") is not False
            or book.get("execution_enabled") is not False
            or book.get("provenance") != "fixed_https_public_endpoint"):
        raise ShortlistProviderIntegrityError("Coinbase public acquisition integrity mismatch")
    snapshot = book.get("snapshot")
    if not isinstance(snapshot, Mapping) or snapshot.get("symbol") != product_id:
        raise ShortlistProviderIntegrityError("Coinbase book instrument identity mismatch")
    combined = reconcile_liquidity(
        market_row, snapshot, now=now,
        max_spread_bps=max_spread_bps,
        min_depth_quote_each_side=min_depth_quote_each_side,
    )
    # Do not promote provider reachability to risk clearance, independently
    # trusted market provenance, or an execution-quality liquidity guarantee.
    return {
        **combined,
        "acquisition": {
            "provider": "coinbase",
            "endpoint": PUBLIC_BOOK_URL,
            "method": "GET",
            "credential_required": False,
            "fixed_https_route": True,
            "market_row_authentication": "not_verified",
        },
        "execution_enabled": False,
    }
