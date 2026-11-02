"""Deterministic, read-only evaluation of CIN informational alert rules.

This module evaluates supplied observations only. It does not fetch data, persist state,
send notifications, or trigger financial actions.
"""
from __future__ import annotations

import math
from typing import Any

SUPPORTED_OPERATORS = {"above", "below", "crosses_above", "crosses_below"}


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def evaluate_alert_rule(
    rule: dict[str, Any],
    observation: dict[str, Any],
    previous_observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a stable evaluation result for a rule and a supplied observation.

    A threshold is evaluated only when the observation is fresh, valid, comparable,
    and non-conflicted. Crossing rules need a prior eligible observation; that first
    eligible sample is a baseline, not a crossing.
    """
    rule_id = rule.get("rule_id")
    operator = rule.get("operator")
    threshold = rule.get("threshold")
    unit = rule.get("unit")
    base = {
        "rule_id": rule_id,
        "operator": operator,
        "threshold": threshold,
        "unit": unit,
        "triggered": False,
    }

    if not isinstance(rule_id, str) or not rule_id.strip():
        return {**base, "status": "invalid_rule", "reason": "rule_id_required"}
    if rule.get("enabled", True) is not True:
        return {**base, "status": "disabled", "reason": "rule_disabled"}
    if operator not in SUPPORTED_OPERATORS:
        return {**base, "status": "invalid_rule", "reason": "unsupported_operator"}
    if not _number(threshold):
        return {**base, "status": "invalid_rule", "reason": "threshold_must_be_finite_number"}
    if not isinstance(unit, str) or not unit.strip():
        return {**base, "status": "invalid_rule", "reason": "unit_required"}

    status = observation.get("freshness_status")
    if observation.get("conflict_status") == "material_conflict":
        return {**base, "status": "ineligible", "reason": "material_source_conflict"}
    if status != "fresh":
        return {**base, "status": "ineligible", "reason": "observation_not_fresh"}
    value = observation.get("value")
    if not _number(value):
        return {**base, "status": "ineligible", "reason": "value_must_be_finite_number"}
    if observation.get("unit") != unit:
        return {**base, "status": "ineligible", "reason": "unit_mismatch"}

    triggered = False
    if operator == "above":
        triggered = value > threshold
    elif operator == "below":
        triggered = value < threshold
    else:
        if previous_observation is None:
            return {**base, "status": "baseline", "reason": "previous_observation_required", "observed_value": value}
        if previous_observation.get("freshness_status") != "fresh":
            return {**base, "status": "baseline", "reason": "previous_observation_not_fresh", "observed_value": value}
        previous_value = previous_observation.get("value")
        if not _number(previous_value) or previous_observation.get("unit") != unit:
            return {**base, "status": "baseline", "reason": "previous_observation_incomparable", "observed_value": value}
        if operator == "crosses_above":
            triggered = previous_value <= threshold and value > threshold
        else:
            triggered = previous_value >= threshold and value < threshold

    return {
        **base,
        "status": "triggered" if triggered else "not_triggered",
        "reason": "condition_met" if triggered else "condition_not_met",
        "triggered": triggered,
        "observed_value": value,
        "observation_id": observation.get("observation_id"),
        "observed_at": observation.get("observed_at"),
        "retrieved_at": observation.get("retrieved_at"),
        "source_id": observation.get("source_id"),
    }

from datetime import datetime, timezone
from typing import Mapping

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


def evaluate_durable_alert_rule(
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
