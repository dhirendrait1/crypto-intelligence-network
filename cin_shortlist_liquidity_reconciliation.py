"""Read-only join of CIN market snapshots and Level 2 liquidity diagnostics.

No provider calls or order execution. Supplied source names do not establish
authenticity. Positive liquidity claims remain unverified until a trusted
provider adapter can attest identity and snapshot integrity.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from cin_shortlist_market_snapshot import assess_market_snapshot
from cin_shortlist_orderbook_liquidity import assess_order_book


def reconcile_liquidity(
    market_row: Mapping[str, Any],
    orderbook: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_spread_bps: Any = "30",
    min_depth_quote_each_side: Any = "10000",
) -> dict[str, Any]:
    """Join independently validated evidence without granting false eligibility.

    Identity is matched in the explicit BASE-QUOTE form. Successful supplied
    diagnostics are *candidates*, never a verified positive gate. A
    structurally valid but stale or shallow book is a negative gate.
    """
    market = assess_market_snapshot(market_row, now=now)
    depth = assess_order_book(
        orderbook, now=now, max_spread_bps=max_spread_bps,
        min_depth_quote_each_side=min_depth_quote_each_side,
    )
    if not isinstance(market["symbol"], str) or not isinstance(market["currency"], str):
        raise ValueError("invalid market identity")
    expected = f'{market["symbol"]}-{market["currency"]}'
    if depth["symbol"] != expected:
        raise ValueError("order-book market identity does not match supplied market row")
    # A named source in caller-supplied material cannot itself authenticate
    # provider ownership, completeness or instrument identity.
    observed_positive = bool(depth["liquidity_sufficient"])
    negative = not market["market_data_fresh"] or not observed_positive
    return {
        "symbol": market["symbol"],
        "market": expected,
        "market_data_fresh": market["market_data_fresh"],
        "book_snapshot_fresh": depth["snapshot_fresh"],
        "reported_orderbook_pass": observed_positive,
        "eligibility_evidence": {
            "data_reliable": market["market_data_fresh"],
            "liquidity_sufficient": False if negative else None,
            "security_clear": None,
            "risk_acceptable": None,
        },
        "eligibility_status": "rejected" if negative else "insufficient_data",
        "provider_authentication": "unverified_caller_supplied",
        "reason": (
            "Stale, shallow or excessively wide market evidence"
            if negative else
            "Reported liquidity passes provisional thresholds but source authenticity and other gates are unverified"
        ),
        "diagnostics": {
            "orderbook_source": depth["source"],
            "orderbook_observed_at": depth["observed_at"],
            "spread_bps": depth["spread_bps"],
            "bid_depth_quote": depth["bid_depth_quote"],
            "ask_depth_quote": depth["ask_depth_quote"],
        },
    }
