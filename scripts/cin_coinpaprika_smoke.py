"""Manual, read-only CoinPaprika public ticker-list smoke check for CIN.

Run from the repository root:
    python scripts/cin_coinpaprika_smoke.py

This performs one unauthenticated GET request only. It does not place orders,
access wallets, or use paid services.
"""
from __future__ import annotations

import json
import math
import sys
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

BASE_URL = "https://api.coinpaprika.com/v1/tickers?quotes=USD"
TIMEOUT_SECONDS = 12
MAX_RESPONSE_BYTES = 5_000_000


def _get_json(url: str) -> list[Any]:
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
    if not isinstance(payload, list):
        raise RuntimeError("provider_invalid_payload")
    return payload


def _finite_number(value: Any, *, positive: bool = False) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or (positive and number <= 0):
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


def inspect_tickers(rows: list[Any]) -> dict[str, Any]:
    valid_identity_rows = [
        row for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("id"), str) and row["id"].strip()
        and isinstance(row.get("symbol"), str) and row["symbol"].strip()
        and isinstance(row.get("name"), str) and row["name"].strip()
    ]
    bitcoin = next((row for row in valid_identity_rows if row.get("id") == "btc-bitcoin"), None)
    quote = bitcoin.get("quotes", {}).get("USD") if bitcoin else None
    if not isinstance(quote, dict):
        quote = {}

    checks = {
        "ticker_list_nonempty": bool(rows),
        "ticker_rows_have_identity": bool(valid_identity_rows),
        "bitcoin_present": bitcoin is not None,
        "bitcoin_usd_price_positive_finite": _finite_number(quote.get("price"), positive=True) is not None,
        "bitcoin_market_cap_finite_nonnegative": (
            _finite_number(quote.get("market_cap")) is not None
            and _finite_number(quote.get("market_cap")) >= 0
        ),
        "bitcoin_volume_24h_finite_nonnegative": (
            _finite_number(quote.get("volume_24h")) is not None
            and _finite_number(quote.get("volume_24h")) >= 0
        ),
        "bitcoin_source_timestamp_timezone_aware": (
            _timestamp_is_aware(bitcoin.get("last_updated")) if bitcoin else False
        ),
    }
    return {
        "provider": "CoinPaprika public API",
        "endpoint": "/v1/tickers?quotes=USD",
        "read_only": True,
        "authentication_used": False,
        "returned_row_count": len(rows),
        "valid_identity_row_count": len(valid_identity_rows),
        "checks": checks,
        "passed": all(checks.values()),
        "coverage_note": "Unauthenticated ticker-list coverage is limited to the provider's top 2,000 coins; this is not a full token catalogue.",
    }


def main() -> int:
    try:
        rows = _get_json(BASE_URL)
        report = inspect_tickers(rows)
    except RuntimeError as exc:
        report = {
            "provider": "CoinPaprika public API",
            "endpoint": "/v1/tickers?quotes=USD",
            "read_only": True,
            "passed": False,
            "error": str(exc),
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
