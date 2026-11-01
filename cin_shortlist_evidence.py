"""Source and freshness validation for CIN shortlist factor evidence.

No external calls. This module bridges source-attributed analyst/provider snapshots
to the deterministic scoring core; it never invents missing values.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from cin_shortlist_scoring import WEIGHTS, assess_candidate

DEFAULT_MAX_AGE = timedelta(hours=24)


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise ValueError("observed_at must be a bounded ISO 8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid observed_at timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at must include timezone")
    return parsed.astimezone(timezone.utc)


def assess_evidence(
    symbol: str,
    factors: Mapping[str, Any],
    gates: Mapping[str, bool],
    *,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_MAX_AGE,
) -> dict:
    """Evaluate source-attributed scores; stale factors remain unscored.

    Factor schema: {factor: {score: 0..100, source: nonempty string,
    observed_at: ISO8601}}. This does not independently verify a source.
    """
    if not isinstance(factors, Mapping):
        raise ValueError("factors must be a mapping")
    if not isinstance(max_age, timedelta) or not timedelta(0) < max_age <= timedelta(days=7):
        raise ValueError("max_age must be greater than zero and at most 7 days")
    current = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    scores = {}
    stale = []
    source_map = {}
    for name, item in factors.items():
        if name not in WEIGHTS:
            raise ValueError("unknown factor")
        if not isinstance(item, Mapping) or set(item) != {"score", "source", "observed_at"}:
            raise ValueError(f"{name}: expected score, source and observed_at")
        source = item["source"]
        if not isinstance(source, str) or not source.strip() or len(source) > 160 or any(ord(ch) < 32 for ch in source):
            raise ValueError(f"{name}: invalid source")
        observed_at = _parse_time(item["observed_at"])
        if observed_at > current:
            raise ValueError(f"{name}: future observed_at")
        if current - observed_at > max_age:
            stale.append(name)
        else:
            scores[name] = item["score"]
        source_map[name] = {"source": source, "observed_at": observed_at.isoformat()}
    result = assess_candidate(symbol, scores, gates)
    return {**result, "stale_factors": sorted(stale), "factor_sources": source_map,
            "source_verification": "supplied_not_independently_verified"}
