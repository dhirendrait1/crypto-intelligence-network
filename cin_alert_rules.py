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
