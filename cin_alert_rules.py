"""Deterministic, read-only CIN alert-rule evaluation primitives."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping


def _aware_datetime(value: Any, field: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include an explicit timezone")
    return value.astimezone(timezone.utc)


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def evaluate_alert_rule(
    rule: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    now: datetime | str,
    last_triggered_at: datetime | str | None = None,
    last_event_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate one threshold rule against one observation without side effects.

    Rule: id, metric, operator ('above'/'below'), threshold, optional cooldown_seconds.
    Observation: id, metric, finite numeric value, observed_at with timezone.
    Callers are responsible for durable state, scheduling and notification delivery.
    """
    if not isinstance(rule, Mapping) or not isinstance(observation, Mapping):
        raise ValueError("rule and observation must be mappings")
    rule_id, metric = rule.get("id"), rule.get("metric")
    if not isinstance(rule_id, str) or not rule_id.strip() or len(rule_id) > 100:
        raise ValueError("rule.id must be a non-empty string of at most 100 characters")
    if not isinstance(metric, str) or not metric.strip() or len(metric) > 100:
        raise ValueError("rule.metric must be a non-empty string of at most 100 characters")
    operator = rule.get("operator")
    if operator not in ("above", "below"):
        raise ValueError("rule.operator must be 'above' or 'below'")
    threshold = _finite_number(rule.get("threshold"), "rule.threshold")
    cooldown = rule.get("cooldown_seconds", 0)
    if isinstance(cooldown, bool) or not isinstance(cooldown, int) or not 0 <= cooldown <= 86400:
        raise ValueError("rule.cooldown_seconds must be an integer from 0 through 86400")
    event_id = observation.get("id")
    if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 200:
        raise ValueError("observation.id must be a non-empty string of at most 200 characters")
    if observation.get("metric") != metric:
        raise ValueError("observation.metric must match rule.metric")
    value = _finite_number(observation.get("value"), "observation.value")
    current_time = _aware_datetime(now, "now")
    observed_at = _aware_datetime(observation.get("observed_at"), "observation.observed_at")
    if observed_at > current_time:
        raise ValueError("observation.observed_at cannot be in the future")
    matched = value > threshold if operator == "above" else value < threshold
    base = {
        "rule_id": rule_id, "metric": metric, "observation_id": event_id,
        "value": value, "threshold": threshold, "operator": operator,
        "observed_at": observed_at.isoformat(), "evaluated_at": current_time.isoformat(),
        "matched": matched, "trigger": False,
    }
    if not matched:
        return {**base, "status": "not_triggered", "reason": "threshold_not_crossed"}
    if last_event_id is not None and event_id == last_event_id:
        return {**base, "status": "deduplicated", "reason": "observation_already_processed"}
    if last_triggered_at is not None and cooldown:
        previous = _aware_datetime(last_triggered_at, "last_triggered_at")
        elapsed = (current_time - previous).total_seconds()
        if elapsed < 0:
            raise ValueError("last_triggered_at cannot be in the future")
        if elapsed < cooldown:
            return {
                **base, "status": "cooldown", "reason": "cooldown_active",
                "cooldown_remaining_seconds": round(cooldown - elapsed, 3),
            }
    return {**base, "status": "triggered", "reason": "threshold_crossed", "trigger": True}
