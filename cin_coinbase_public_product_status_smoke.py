"""One-shot, redacted Coinbase public product-status probe; no accounts or orders."""
from __future__ import annotations

import argparse
import json
from typing import Any

from cin_coinbase_public_product_status import fetch_coinbase_public_product_status

ALLOWED_PRODUCTS = ("BTC-USD", "ETH-USD")


def probe(product_id: str) -> dict[str, Any]:
    if product_id not in ALLOWED_PRODUCTS:
        raise ValueError("unsupported smoke product")
    status = fetch_coinbase_public_product_status(product_id)
    if (status.get("provider") != "coinbase"
        or status.get("product_id") != product_id
        or status.get("request_method") != "GET"
        or status.get("authenticated") is not False
        or status.get("execution_enabled") is not False):
        raise ValueError("source or read-only identity mismatch")
    return {
        "product_id": product_id,
        "status": "pass" if status["market_available_for_research"] else "not_eligible",
        "product_status": status["status"],
        "product_type": status["product_type"],
        "flags": status["flags"],
        "provider": "coinbase",
        "operation": "public_get_only",
        "production_activated": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CIN one-shot public Coinbase status smoke")
    parser.add_argument("--product", default="BTC-USD", choices=ALLOWED_PRODUCTS)
    args = parser.parse_args(argv)
    try:
        result = probe(args.product)
    except (ValueError, OSError, TimeoutError):
        print(json.dumps({
            "status": "fail", "product_id": args.product,
            "category": "public_product_or_contract_error",
            "production_activated": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
