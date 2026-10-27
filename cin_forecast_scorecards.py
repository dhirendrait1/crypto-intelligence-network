"""Deterministic aggregation of already-evaluated CIN forecast outcomes.

This module computes descriptive error metrics only. It does not claim probabilistic
calibration, infer missing outcomes, fetch observations, or mutate forecast records.
"""
from __future__ import annotations

import math
from typing import Any


def build_forecast_scorecard(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate valid evaluated outcomes into reproducible error metrics.

    Each accepted row must have status='evaluated', a metric and unit, and finite
    numeric predicted_value/actual_value/error/absolute_error. Rows with different
    metric or unit are not pooled. Missing/invalid rows are counted as excluded.
    """
    if not isinstance(outcomes, list):
        return {"status": "invalid_input", "reason": "outcomes_must_be_list"}

    accepted: list[dict[str, Any]] = []
    excluded = 0
    group: tuple[str, str] | None = None
    for row in outcomes:
        if not isinstance(row, dict) or row.get("status") != "evaluated":
            excluded += 1
            continue
        metric, unit = row.get("metric"), row.get("unit")
        nums = [row.get(k) for k in ("predicted_value", "actual_value", "error", "absolute_error")]
        if (not isinstance(metric, str) or not metric.strip()
                or not isinstance(unit, str) or not unit.strip()
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in nums)):
            excluded += 1
            continue
        this_group = (metric, unit)
        if group is None:
            group = this_group
        if this_group != group:
            excluded += 1
            continue
        # Recompute error from values to avoid trusting inconsistent stored metrics.
        error = float(row["actual_value"]) - float(row["predicted_value"])
        accepted.append({
            "error": error,
            "absolute_error": abs(error),
            "squared_error": error * error,
            "actual_value": float(row["actual_value"]),
        })

    if not accepted:
        return {
            "status": "insufficient_data",
            "reason": "no_comparable_evaluated_outcomes",
            "sample_count": 0,
            "excluded_count": excluded,
        }

    n = len(accepted)
    errors = [r["error"] for r in accepted]
    absolute_errors = [r["absolute_error"] for r in accepted]
    squared_errors = [r["squared_error"] for r in accepted]
    percentage_errors = [
        r["absolute_error"] / abs(r["actual_value"]) * 100.0
        for r in accepted if r["actual_value"] != 0
    ]
    return {
        "status": "computed",
        "metric": group[0],
        "unit": group[1],
        "sample_count": n,
        "excluded_count": excluded,
        "mean_error": sum(errors) / n,
        "mean_absolute_error": sum(absolute_errors) / n,
        "root_mean_squared_error": math.sqrt(sum(squared_errors) / n),
        "mean_absolute_percentage_error": (
            sum(percentage_errors) / len(percentage_errors) if percentage_errors else None
        ),
        "percentage_error_sample_count": len(percentage_errors),
        "percentage_error_excluded_zero_actual_count": n - len(percentage_errors),
        "interpretation": "descriptive_historical_errors_not_a_probability_or_guarantee",
    }
