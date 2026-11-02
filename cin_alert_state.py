"""Pure helpers for deterministic CIN alert deduplication and cooldown decisions.

The caller owns durable storage and concurrency control. This module performs no I/O
and sends no notifications or financial actions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def alert_deduplication_key(rule_id: str, observation_id: str, condition_code: str) -> str:
    """Create a stable, unambiguous key for one rule/observation/condition tuple."""
    parts = (rule_id, observation_id, condition_code)
    if any(not isinstance(part, str) or not part.strip() for part in parts):
        raise ValueError("rule_id, observation_id, and condition_code must be non-empty strings")
    # Length-prefix fields so separators inside caller-provided IDs cannot collide.
    return "|".join(f"{len(part)}:{part}" for part in parts)


def decide_alert_emission(
    *,
    deduplication_key: str,
    now: str,
    cooldown_seconds: int,
    prior_emitted_at: str | None = None,
    already_emitted: bool = False,
) -> dict[str, Any]:
    """Decide whether an alert event may be emitted, without persisting or delivering it."""
    base = {"deduplication_key": deduplication_key, "emit": False}
    if not isinstance(deduplication_key, str) or not deduplication_key.strip():
        return {**base, "status": "invalid_input", "reason": "deduplication_key_required"}
    if isinstance(cooldown_seconds, bool) or not isinstance(cooldown_seconds, int) or cooldown_seconds < 0:
        return {**base, "status": "invalid_input", "reason": "cooldown_must_be_nonnegative_integer"}
    now_dt = _parse_time(now)
    if now_dt is None:
        return {**base, "status": "invalid_input", "reason": "now_must_be_timezone_aware"}
    if already_emitted:
        return {**base, "status": "suppressed", "reason": "duplicate_event"}
    if prior_emitted_at is None:
        return {**base, "status": "eligible", "reason": "no_prior_emission", "emit": True}
    prior_dt = _parse_time(prior_emitted_at)
    if prior_dt is None:
        return {**base, "status": "suppressed", "reason": "prior_emission_time_unknown"}
    elapsed = (now_dt - prior_dt).total_seconds()
    if elapsed < 0:
        return {**base, "status": "suppressed", "reason": "clock_or_event_time_regression"}
    if elapsed < cooldown_seconds:
        return {
            **base,
            "status": "suppressed",
            "reason": "cooldown_active",
            "cooldown_remaining_seconds": int(cooldown_seconds - elapsed + 0.999999),
        }
    return {**base, "status": "eligible", "reason": "cooldown_elapsed", "emit": True}
