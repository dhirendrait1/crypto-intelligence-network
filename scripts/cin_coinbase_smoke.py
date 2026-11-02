"""Manual, read-only Coinbase Exchange public API smoke check for CIN.

Run from the repository root:
    python scripts/cin_coinbase_smoke.py

This performs GET requests only. It uses no credentials and never places orders.
"""
from __future__ import annotations

import json
import math
import sys
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

BASE_URL = "https://api.exchange.coinbase.com"
PRODUCTS = {"bitcoin": "BTC-USD", "ethereum": "ETH-USD"}
TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 256_000


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "CIN-read-only-smoke/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("provider_request_failed") from exc

    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("provider_response_too_large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("provider_invalid_json") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("provider_invalid_payload")
    return payload


def _positive_finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def _timestamp_is_aware(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def check_product(asset: str, product_id: str) -> dict[str, Any]:
    base = f"{BASE_URL}/products/{product_id}"
    stats = _get_json(f"{base}/stats")
    ticker = _get_json(f"{base}/ticker")

    last = _positive_finite(stats.get("last"))
    opening = _positive_finite(stats.get("open"))
    volume = stats.get("volume")
    try:
        volume_number = float(volume) if not isinstance(volume, bool) else math.nan
    except (TypeError, ValueError, OverflowError):
        volume_number = math.nan

    checks = {
        "stats_last_positive_finite": last is not None,
        "stats_open_positive_finite": opening is not None,
        "stats_volume_finite_nonnegative": math.isfinite(volume_number) and volume_number >= 0,
        "ticker_timestamp_timezone_aware": _timestamp_is_aware(ticker.get("time")),
    }
    return {
        "asset": asset,
        "product_id": product_id,
        "checks": checks,
        "passed": all(checks.values()),
        "volume_unit": asset.upper(),
        "note": "24-hour volume is base-asset-denominated, not USD quote turnover.",
    }


def main() -> int:
    results = []
    for asset, product_id in PRODUCTS.items():
        try:
            results.append(check_product(asset, product_id))
        except RuntimeError as exc:
            results.append({
                "asset": asset,
                "product_id": product_id,
                "passed": False,
                "error": str(exc),
            })

    report = {"provider": "Coinbase Exchange public API", "read_only": True, "results": results}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if all(item.get("passed") for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
