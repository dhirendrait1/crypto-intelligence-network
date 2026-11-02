"""Validate provenance metadata for read-only CIN source observations.

This module validates a caller-supplied envelope only. It performs no network
requests and does not prove source authenticity or market-data correctness.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from datetime import datetime
from typing import Any


ALLOWED_TIMESTAMP_SEMANTICS = {
    "candle_open_time",
    "candle_close_time",
    "publication_time",
    "block_time",
    "snapshot_time",
    "source_event_time",
}


@dataclass(frozen=True)
class SourceObservation:
    source_id: str
    subject: str
    observed_at: str
    retrieved_at: str
    timestamp_semantics: str
    provenance: str
    quote_currency: str | None = None
    interval: str | None = None


def _parse_aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def validate_source_observation(observation: Any, *, now: datetime) -> dict[str, Any]:
    """Return normalized validation metadata; missing/ambiguous evidence is unknown."""
    if now.tzinfo is None or now.utcoffset() is None:
        return {"validity": "unknown", "reason": "timezone_required_for_clock"}

    if not isinstance(observation, dict):
        return {"validity": "unknown", "reason": "observation_must_be_mapping"}

    required = ("source_id", "subject", "observed_at", "retrieved_at",
                "timestamp_semantics", "provenance")
    missing = [key for key in required if not isinstance(observation.get(key), str)
               or not observation.get(key, "").strip()]
    if missing:
        return {"validity": "unknown", "reason": "missing_required_fields", "missing": missing}

    semantics = observation["timestamp_semantics"].strip()
    if semantics not in ALLOWED_TIMESTAMP_SEMANTICS:
        return {"validity": "unknown", "reason": "unknown_timestamp_semantics"}

    observed = _parse_aware(observation["observed_at"])
    retrieved = _parse_aware(observation["retrieved_at"])
    if observed is None or retrieved is None:
        return {"validity": "unknown", "reason": "invalid_or_timezone_naive_timestamp"}

    if retrieved > now:
        return {"validity": "unknown", "reason": "retrieval_timestamp_in_future"}
    if observed > now:
        return {"validity": "unknown", "reason": "observation_timestamp_in_future"}
    if observed > retrieved:
        return {"validity": "unknown", "reason": "observation_after_retrieval"}

    quote_currency = observation.get("quote_currency")
    interval = observation.get("interval")
    if semantics in {"candle_open_time", "candle_close_time"}:
        if not isinstance(quote_currency, str) or not quote_currency.strip():
            return {"validity": "unknown", "reason": "market_candle_quote_currency_required"}
        if not isinstance(interval, str) or not interval.strip():
            return {"validity": "unknown", "reason": "market_candle_interval_required"}

    return {
        "validity": "valid_metadata",
        "reason": "required_provenance_present",
        "source_id": observation["source_id"].strip(),
        "subject": observation["subject"].strip(),
        "observed_at": observed.isoformat(),
        "retrieved_at": retrieved.isoformat(),
        "timestamp_semantics": semantics,
        "provenance": observation["provenance"].strip(),
        "quote_currency": quote_currency.strip() if isinstance(quote_currency, str) else None,
        "interval": interval.strip() if isinstance(interval, str) else None,
        "age_seconds_at_retrieval": math.ceil((retrieved - observed).total_seconds()),
        "freshness_assessed": False,
        "source_authenticity_verified": False,
    }
