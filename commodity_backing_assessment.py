"""CIN commodity-backed asset evidence assessment (read-only).

This module records evidence metadata; it does not independently certify reserves,
custody, issuer solvency, or redemption rights. Missing evidence is never proof
that backing exists.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

VALID_STATUSES = {"verified", "unverified", "stale", "unavailable"}
REQUIRED_EVIDENCE_FIELDS = (
    "evidence_type",
    "source_name",
    "source_url",
    "published_at",
    "checked_at",
    "status",
)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_evidence(item: dict[str, Any], *, now: datetime | None = None,
                       max_age_days: int = 90) -> dict[str, Any]:
    """Validate one evidence record and derive freshness without inventing proof.

    'verified' is accepted only as a supplied review status with a source URL,
    source name, and parseable publication/check timestamps. This is metadata
    validation, not an independent audit of the source's claims.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)

    record = {field: item.get(field) for field in REQUIRED_EVIDENCE_FIELDS}
    record["notes"] = str(item.get("notes", "")).strip() or None
    status = str(record.get("status") or "unverified").lower()
    if status not in VALID_STATUSES:
        status = "unverified"

    published = _parse_timestamp(record.get("published_at"))
    checked = _parse_timestamp(record.get("checked_at"))
    missing = [
        field for field in ("evidence_type", "source_name", "source_url")
        if not isinstance(record.get(field), str) or not record[field].strip()
    ]
    if published is None:
        missing.append("published_at")
    if checked is None:
        missing.append("checked_at")

    if status == "verified" and (missing or not str(record.get("source_url", "")).startswith(("https://", "http://"))):
        status = "unverified"
        record["status_reason"] = "Verification metadata incomplete; source claims have not been independently certified by CIN."
    elif status == "verified":
        record["status_reason"] = "Marked verified by the supplied reviewer metadata; CIN has not independently audited the underlying claim."
    elif status == "unavailable":
        record["status_reason"] = "Evidence could not be obtained; this does not prove backing is absent or present."
    elif status == "stale":
        record["status_reason"] = "Evidence is explicitly marked stale; re-check the source before relying on it."
    else:
        record["status_reason"] = "Evidence is not verified."

    age_days = None
    if published is not None:
        age_days = max(0, (current - published).days)
        if status == "verified" and age_days > max_age_days:
            status = "stale"
            record["status_reason"] = f"Publication is older than the {max_age_days}-day freshness threshold."

    record["status"] = status
    record["publication_age_days"] = age_days
    record["missing_fields"] = missing
    record["freshness_threshold_days"] = max_age_days
    return record


def assess_commodity_asset(symbol: str, evidence: list[dict[str, Any]], *,
                           now: datetime | None = None,
                           max_age_days: int = 90) -> dict[str, Any]:
    """Summarize reserve/redemption/custody evidence without treating gaps as proof."""
    required_types = {
        "reserve_attestation",
        "redemption_terms",
        "custody_or_issuer_disclosure",
    }
    normalized = [
        normalize_evidence(item, now=now, max_age_days=max_age_days)
        for item in evidence
    ]
    by_type: dict[str, list[dict[str, Any]]] = {kind: [] for kind in required_types}
    for item in normalized:
        kind = item.get("evidence_type")
        if kind in by_type:
            by_type[kind].append(item)

    coverage = {}
    for kind, records in by_type.items():
        if any(record["status"] == "verified" for record in records):
            state = "verified"
        elif any(record["status"] == "stale" for record in records):
            state = "stale"
        elif any(record["status"] == "unavailable" for record in records):
            state = "unavailable"
        else:
            state = "unverified"
        coverage[kind] = {"status": state, "evidence_count": len(records)}

    statuses = [value["status"] for value in coverage.values()]
    if all(status == "verified" for status in statuses):
        overall = "evidence_coverage_complete"
    elif "stale" in statuses:
        overall = "evidence_stale_or_incomplete"
    elif "unavailable" in statuses:
        overall = "evidence_unavailable_or_incomplete"
    else:
        overall = "evidence_unverified_or_incomplete"

    return {
        "symbol": symbol.upper().strip(),
        "assessment_type": "commodity_backing_evidence_review",
        "mode": "read_only",
        "overall_status": overall,
        "not_a_reserve_certification": True,
        "evidence_coverage": coverage,
        "evidence": normalized,
        "limitations": [
            "CIN records evidence metadata; it does not itself audit reserves or certify issuer claims.",
            "A source publication or attestation is not a guarantee of solvency, custody, redemption, or future backing.",
            "Missing evidence is unknown, not proof of backing or lack of backing.",
            "Redemption availability may vary by jurisdiction, customer eligibility, minimum size, fees, and issuer terms.",
        ],
    }
