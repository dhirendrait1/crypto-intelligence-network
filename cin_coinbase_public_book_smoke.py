"""One-shot, credential-free Coinbase public order-book smoke check.

Prints bounded status metadata, not raw prices, order-book levels, credentials
or private endpoints. Exits non-zero on transport, contract or freshness failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from cin_coinbase_public_orderbook import PublicBookError, fetch_coinbase_public_book

ALLOWED_PRODUCTS = ("BTC-USD", "ETH-USD")


def probe(product_id: str) -> dict[str, Any]:
    if product_id not in ALLOWED_PRODUCTS:
        raise ValueError("probe product must be BTC-USD or ETH-USD")
    result = fetch_coinbase_public_book(product_id)
    checks = result["diagnostics"]
    if (result["provider"] != "coinbase" or result["product_id"] != product_id
            or result["request_method"] != "GET" or result["execution_enabled"] is not False
            or result["authenticated"] is not False):
        raise PublicBookError("provider identity or read-only boundary failed")
    return {
        "product_id": product_id,
        "provider": "coinbase",
        "operation": "public_read_only_get",
        "snapshot_fresh": checks["snapshot_fresh"],
        "age_seconds": checks["age_seconds"],
        "level_counts": {
            "bids": len(result["snapshot"]["bids"]),
            "asks": len(result["snapshot"]["asks"]),
        },
        "status": "pass" if checks["snapshot_fresh"] else "stale_snapshot",
        "price_data_included": False,
        "production_activated": False,
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CIN public Coinbase one-shot smoke check")
    parser.add_argument("--product", choices=ALLOWED_PRODUCTS, default="BTC-USD")
    args = parser.parse_args(argv)
    try:
        result = probe(args.product)
    except (PublicBookError, ValueError, OSError, TimeoutError) as exc:
        # Never dump raw provider responses or user environment into logs.
        category = "provider_or_contract_error"
        if isinstance(exc, OSError):
            category = "transport_error"
        print(json.dumps({
            "status": "fail", "category": category, "product_id": args.product,
            "operation": "public_read_only_get", "production_activated": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(run())
