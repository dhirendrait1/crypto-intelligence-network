"""Pure evaluation helpers for completed CIN forecasts.

Evaluation is retrospective and read-only. It does not generate forecasts, fetch
observations, mutate records, or place trades.
"""
from __future__ import annotations

import math
from typing import Any


def evaluate_forecast_outcome(
    forecast: dict[str, Any],
    actual: dict[str, Any],
) -> dict[str, Any]:
    """Compare a forecast target with an actual observation after its horizon closes.

    Required forecast fields: forecast_id, metric, value, unit, target_at.
    Required actual fields: observation_id, metric, value, unit, observed_at, source_id.
    Timestamps must be ISO-8601 strings with explicit timezone offsets.
    """
    base = {
        "forecast_id": forecast.get("forecast_id") if isinstance(forecast, dict) else None,
        "observation_id": actual.get("observation_id") if isinstance(actual, dict) else None,
        "status": "not_evaluable",
    }
    if not isinstance(forecast, dict) or not isinstance(actual, dict):
        return {**base, "reason": "records_must_be_objects"}

    for obj, keys, label in (
        (forecast, ("forecast_id", "metric", "unit", "target_at"), "forecast"),
        (actual, ("observation_id", "metric", "unit", "observed_at", "source_id"), "actual"),
    ):
        if any(not isinstance(obj.get(key), str) or not obj[key].strip() for key in keys):
            return {**base, "reason": f"{label}_metadata_missing"}
    if forecast["metric"] != actual["metric"]:
        return {**base, "reason": "metric_mismatch"}
    if forecast["unit"] != actual["unit"]:
        return {**base, "reason": "unit_mismatch"}

    predicted, observed = forecast.get("value"), actual.get("value")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in (predicted, observed)):
        return {**base, "reason": "values_must_be_finite_numbers"}

    target_at = _parse_time(forecast["target_at"])
    observed_at = _parse_time(actual["observed_at"])
    if target_at is None or observed_at is None:
        return {**base, "reason": "timestamps_must_be_timezone_aware"}
    if observed_at < target_at:
        return {**base, "reason": "observation_precedes_forecast_horizon"}
    error = float(observed - predicted)
    result = {
        **base,
        "status": "evaluated",
        "reason": "horizon_observation_comparable",
        "metric": forecast["metric"],
        "unit": forecast["unit"],
        "predicted_value": float(predicted),
        "actual_value": float(observed),
        "error": error,
        "absolute_error": abs(error),
        "source_id": actual["source_id"],
        "target_at": forecast["target_at"],
        "observed_at": actual["observed_at"],
    }
    # Percentage error is undefined for a zero actual; never divide by zero.
    if observed != 0:
        result["absolute_percentage_error"] = abs(error) / abs(float(observed)) * 100.0
    else:
        result["absolute_percentage_error"] = None
        result["percentage_error_reason"] = "actual_value_is_zero"
    return result


def _parse_time(value: str):
    from datetime import datetime

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed
