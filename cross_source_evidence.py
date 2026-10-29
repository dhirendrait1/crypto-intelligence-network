"""Conservative cross-source metric comparison for CIN (read-only).

This module compares caller-supplied observations. It does not rank sources,
authenticate identities, infer source independence, or certify the underlying metric.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any
from urllib.parse import urlsplit


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (OverflowError, TypeError, ValueError):
        return None


def _source_identity(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        port = parsed.port
        scheme = parsed.scheme.lower()
        host = parsed.hostname.lower()
        if port is not None and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
            host = f"{host}:{port}"
        return f"{scheme}://{host}{parsed.path.rstrip('/') or '/'}" + (f"?{parsed.query}" if parsed.query else "")
    except ValueError:
        return None


def compare_metric_observations(
    observations: list[dict[str, Any]],
    *,
    absolute_tolerance: float = 0.0,
    relative_tolerance: float = 0.01,
    comparison_window_seconds: int = 300,
) -> dict[str, Any]:
    """Group comparable metric observations and expose disagreement without source ranking."""
    if not isinstance(observations, list):
        raise ValueError("observations must be a list")
    if isinstance(absolute_tolerance, bool) or not isinstance(absolute_tolerance, (int, float)) or not math.isfinite(absolute_tolerance) or absolute_tolerance < 0:
        raise ValueError("absolute_tolerance must be finite and non-negative")
    if isinstance(relative_tolerance, bool) or not isinstance(relative_tolerance, (int, float)) or not math.isfinite(relative_tolerance) or relative_tolerance < 0:
        raise ValueError("relative_tolerance must be finite and non-negative")
    if isinstance(comparison_window_seconds, bool) or not isinstance(comparison_window_seconds, int) or comparison_window_seconds < 0:
        raise ValueError("comparison_window_seconds must be a non-negative integer")

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    rejected_count = 0
    for item in observations:
        if not isinstance(item, dict):
            rejected_count += 1
            continue
        metric = item.get("metric")
        unit = item.get("unit")
        value = item.get("value")
        observed_at = _timestamp(item.get("observed_at"))
        source_name = item.get("source_name")
        source_url = _source_identity(item.get("source_url"))
        if (
            not isinstance(metric, str) or not metric.strip()
            or not isinstance(unit, str) or not unit.strip()
            or isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or observed_at is None
            or not isinstance(source_name, str) or not source_name.strip()
            or source_url is None
        ):
            rejected_count += 1
            continue
        groups.setdefault((metric.strip(), unit.strip()), []).append({
            "value": float(value),
            "observed_at": observed_at,
            "source_name": source_name.strip(),
            "source_identity": source_url,
        })

    results = []
    for (metric, unit), rows in sorted(groups.items()):
        latest = max(row["observed_at"] for row in rows)
        comparable = [row for row in rows if (latest - row["observed_at"]).total_seconds() <= comparison_window_seconds]
        unique_sources: dict[str, dict[str, Any]] = {}
        duplicate_source_observations = 0
        for row in sorted(comparable, key=lambda r: r["observed_at"]):
            if row["source_identity"] in unique_sources:
                duplicate_source_observations += 1
                continue
            unique_sources[row["source_identity"]] = row
        values = [row["value"] for row in unique_sources.values()]
        source_count = len(values)
        median = sorted(values)[source_count // 2] if source_count and source_count % 2 else (
            (sorted(values)[source_count // 2 - 1] + sorted(values)[source_count // 2]) / 2 if source_count else None
        )
        spread = max(values) - min(values) if source_count >= 2 else None
        allowed_spread = max(float(absolute_tolerance), float(relative_tolerance) * abs(median)) if median is not None else None
        if source_count < 2:
            status = "insufficient_independent_source_count"
            confidence = "insufficient_evidence"
        elif spread is not None and spread > allowed_spread:
            status = "conflicting"
            confidence = "low_confidence_conflict"
        else:
            status = "agreement_observed"
            confidence = "limited_corroboration"
        results.append({
            "metric": metric,
            "unit": unit,
            "status": status,
            "confidence_class": confidence,
            "comparable_source_count": source_count,
            "observations_outside_time_window_count": len(rows) - len(comparable),
            "duplicate_source_observation_count": duplicate_source_observations,
            "value_min": min(values) if values else None,
            "value_max": max(values) if values else None,
            "value_median": median,
            "absolute_spread": spread,
            "allowed_spread": allowed_spread,
            "comparison_window_seconds": comparison_window_seconds,
            "source_independence_verified": False,
            "source_roles_authenticated": False,
            "preferred_source_selected": False,
            "source_observations": [
                {
                    "source_name": row["source_name"],
                    "source_url": row["source_identity"],
                    "value": row["value"],
                    "observed_at": row["observed_at"].isoformat(),
                }
                for row in unique_sources.values()
            ],
        })
    return {
        "comparison_mode": "caller_supplied_metric_observations",
        "rejected_observation_count": rejected_count,
        "metric_group_count": len(results),
        "results": results,
        "limitations": [
            "Only caller-supplied observations are compared; CIN does not fetch or independently verify source data.",
            "A matching hostname or distinct URL does not prove independent ownership, authorship, or corroboration.",
            "Source roles and source identities are not authenticated; no source is ranked or preferred.",
            "Only observations within the configured time window are compared; values in different units are never combined.",
            "Tolerance thresholds are explicit comparison heuristics, not market-data accuracy guarantees.",
            "Confidence classes describe evidence agreement only; they are not probabilities or investment recommendations.",
        ],
        "read_only": True,
        "not_a_certification": True,
    }
