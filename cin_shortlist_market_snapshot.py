"""Read-only eligibility bridge for CIN normalized public market snapshots.

No provider calls. This module never infers executable liquidity from reported
24h traded volume, nor maps market snapshots to speculative factor scores.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

MAX_MARKET_AGE_SECONDS = 15 * 60


def assess_market_snapshot(row: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise ValueError("market snapshot must be a mapping")
    required = ("id", "symbol", "price", "currency", "last_updated",
                "freshness_status", "analysis_eligible", "total_volume_24h")
    if any(key not in row for key in required):
        raise ValueError("market snapshot missing required fields")
    symbol = row["symbol"]
    if not isinstance(symbol, str) or not symbol or symbol != symbol.strip() or len(symbol) > 24:
        raise ValueError("invalid market symbol")
    if not isinstance(row["id"], str) or not row["id"] or len(row["id"]) > 100:
        raise ValueError("invalid market identity")
    if not isinstance(row["currency"], str) or not row["currency"]:
        raise ValueError("invalid market quote currency")
    price = row["price"]
    if type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
        raise ValueError("market price must be strictly positive and finite")
    if type(row["analysis_eligible"]) is not bool:
        raise ValueError("analysis_eligible must be a boolean")
    observed = row["last_updated"]
    if not isinstance(observed, str) or len(observed) > 64:
        raise ValueError("invalid last_updated timestamp")
    try:
        stamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid last_updated timestamp") from None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("last_updated must be timezone aware")
    current = datetime.now(timezone.utc) if now is None else now
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone aware")
    stamp = stamp.astimezone(timezone.utc)
    age = (current.astimezone(timezone.utc) - stamp).total_seconds()
    fresh = (0 <= age <= MAX_MARKET_AGE_SECONDS
             and row["freshness_status"] == "fresh"
             and row["analysis_eligible"] is True)
    volume = row["total_volume_24h"]
    volume_valid = (type(volume) in (int, float) and math.isfinite(volume) and volume > 0)
    return {
        "symbol": symbol,
        "market_id": row["id"],
        "currency": row["currency"],
        "observed_at": stamp.isoformat(),
        "market_data_fresh": fresh,
        "market_data_age_seconds": max(0, int(age)) if age >= 0 else None,
        "reported_positive_volume": volume_valid,
        "eligibility_evidence": {
            "data_reliable": True if fresh else False,
            "liquidity_sufficient": None,
            "security_clear": None,
            "risk_acceptable": None,
        },
        "eligibility_status": "insufficient_data",
        "reason": "Market snapshot alone cannot establish security, risk or executable liquidity",
    }
