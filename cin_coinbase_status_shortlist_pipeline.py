"""Coinbase public product-status preflight for read-only shortlist research.

Queries public product metadata before retrieving a public order book.
No trade/order endpoints, account endpoints, credentials, or deployment.
"""
from __future__ import annotations

from typing import Any, Mapping

from cin_coinbase_public_product_status import fetch_coinbase_public_product_status
from cin_coinbase_shortlist_integration import evaluate_coinbase_liquidity
from cin_shortlist_market_snapshot import assess_market_snapshot


def research_liquidity_with_market_status(
    market_row: Mapping[str, Any], **kwargs: Any
) -> dict[str, Any]:
    """Reject inactive or ambiguous Coinbase markets before fetching L2."""
    market = assess_market_snapshot(market_row, now=kwargs.get("now"))
    product_id = f'{market["symbol"]}-{market["currency"]}'
    details = fetch_coinbase_public_product_status(product_id)
    if details.get("product_id") != product_id or details.get("provider") != "coinbase":
        raise ValueError("Coinbase product-status identity mismatch")
    if details.get("execution_enabled") is not False:
        raise ValueError("Coinbase product-status read-only boundary mismatch")
    if details.get("market_available_for_research") is not True:
        return {
            "product_id": product_id,
            "status": "rejected",
            "reason": "Coinbase product is not an eligible active spot market",
            "product_status": details.get("status"),
            "book_requested": False,
            "execution_enabled": False,
        }
    result = evaluate_coinbase_liquidity(market_row, **kwargs)
    # A successful status check never overrides unverified security,
    # independently sourced market data, or liquidity fill uncertainty.
    return {
        **result,
        "product_status": details["status"],
        "product_type": details["product_type"],
        "product_status_verified_from_public_route": True,
        "book_requested": True,
        "execution_enabled": False,
    }
