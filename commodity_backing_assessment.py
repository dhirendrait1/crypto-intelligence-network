"""CIN commodity-backed asset evidence assessment (read-only).

This module records evidence metadata; it does not independently certify reserves,
custody, issuer solvency, or redemption rights. Missing evidence is never proof
that backing exists.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

VALID_STATUSES = {"verified", "unverified", "stale", "unavailable"}
REQUIRED_EVIDENCE_FIELDS = (
    "evidence_type",
    "source_name",
    "source_url",
    "published_at",
    "checked_at",
    "status",
)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _is_http_url(value: Any) -> bool:
    """Accept only absolute HTTP(S) URLs with a hostname and no embedded credentials."""
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value.strip())
        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


def normalize_evidence(item: Any, *, now: datetime | None = None,
                       max_age_days: int = 90) -> dict[str, Any]:
    """Validate one evidence record and derive freshness without inventing proof.

    'verified' is accepted only as a supplied review status with a valid absolute
    HTTP(S) source URL, source name, and parseable publication/check timestamps.
    Future timestamps and impossible publication/check ordering downgrade the
    supplied status. This is metadata validation, not an independent audit.
    """
    threshold_valid = isinstance(max_age_days, int) and not isinstance(max_age_days, bool) and max_age_days >= 0
    max_age_days = max_age_days if threshold_valid else 90
    assessment_clock_valid = (
        now is None
        or (
            isinstance(now, datetime)
            and now.tzinfo is not None
            and now.utcoffset() is not None
        )
    )
    current = now if assessment_clock_valid and now is not None else datetime.now(timezone.utc)
    current = current.astimezone(timezone.utc)

    if not isinstance(item, dict):
        return {
            **{field: None for field in REQUIRED_EVIDENCE_FIELDS},
            "notes": None,
            "status": "unverified",
            "status_reason": "Evidence record must be an object; malformed record was retained for audit.",
            "publication_age_days": None,
            "missing_fields": list(REQUIRED_EVIDENCE_FIELDS),
            "timestamp_validation_errors": [],
            "source_url_valid": False,
            "freshness_threshold_days": max_age_days,
            "assessment_clock_valid": assessment_clock_valid,
            "invalid_record": True,
        }

    record = {field: item.get(field) for field in REQUIRED_EVIDENCE_FIELDS}
    record["notes"] = str(item.get("notes", "")).strip() or None
    record["invalid_record"] = False
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

    timestamp_errors = []
    if published is not None and published > current:
        timestamp_errors.append("published_at_is_in_the_future")
    if checked is not None and checked > current:
        timestamp_errors.append("checked_at_is_in_the_future")
    if published is not None and checked is not None and checked < published:
        timestamp_errors.append("checked_at_precedes_published_at")

    url_valid = _is_http_url(record.get("source_url"))
    if status == "verified" and (missing or not url_valid or timestamp_errors):
        status = "unverified"
        if timestamp_errors:
            record["status_reason"] = "Timestamp chronology is invalid; supplied verification status was downgraded."
        elif not url_valid:
            record["status_reason"] = "Source URL must be an absolute HTTP(S) URL with a hostname and no embedded credentials."
        else:
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
    if published is not None and published <= current:
        age_days = (current - published).days
        if status == "verified" and age_days > max_age_days:
            status = "stale"
            record["status_reason"] = f"Publication is older than the {max_age_days}-day freshness threshold."

    record["status"] = status
    record["publication_age_days"] = age_days
    record["missing_fields"] = missing
    record["timestamp_validation_errors"] = timestamp_errors
    record["source_url_valid"] = url_valid
    record["freshness_threshold_days"] = max_age_days
    record["assessment_clock_valid"] = assessment_clock_valid
    return record


def assess_commodity_asset(symbol: str, evidence: list[dict[str, Any]], *,
                           now: datetime | None = None,
                           max_age_days: int = 90) -> dict[str, Any]:
    """Summarize reserve/redemption/custody evidence without treating gaps as proof."""
    threshold_valid = isinstance(max_age_days, int) and not isinstance(max_age_days, bool) and max_age_days >= 0
    max_age_days = max_age_days if threshold_valid else 90
    assessment_clock_valid = (
        now is None
        or (
            isinstance(now, datetime)
            and now.tzinfo is not None
            and now.utcoffset() is not None
        )
    )
    current = (
        now.astimezone(timezone.utc)
        if assessment_clock_valid and now is not None
        else datetime.now(timezone.utc)
    )
    required_types = {
        "reserve_attestation",
        "redemption_terms",
        "custody_or_issuer_disclosure",
    }
    source_records = evidence if isinstance(evidence, list) else []
    normalized = [
        normalize_evidence(item, now=current, max_age_days=max_age_days)
        for item in source_records
    ]
    for row in normalized:
        row["assessment_clock_valid"] = assessment_clock_valid
    by_type: dict[str, list[dict[str, Any]]] = {kind: [] for kind in required_types}
    for item in normalized:
        kind = item.get("evidence_type")
        if kind in by_type:
            by_type[kind].append(item)

    coverage = {}
    for kind, records in by_type.items():
        distinct_statuses = {record["status"] for record in records}
        if len(distinct_statuses) > 1:
            state = "conflicting"
        elif distinct_statuses == {"verified"}:
            state = "verified"
        elif distinct_statuses == {"stale"}:
            state = "stale"
        elif distinct_statuses == {"unavailable"}:
            state = "unavailable"
        else:
            state = "unverified"
        identities = {
            (
                record.get("evidence_type"),
                str(record.get("source_url") or "").strip().rstrip("/").lower(),
                record.get("published_at"),
                record.get("checked_at"),
            )
            for record in records
        }
        coverage[kind] = {
            "status": state,
            "evidence_count": len(identities),
            "duplicate_record_count": max(0, len(records) - len(identities)),
            "conflict_detected": state == "conflicting",
        }

    statuses = [value["status"] for value in coverage.values()]
    if "conflicting" in statuses:
        overall = "evidence_conflicting_or_incomplete"
    elif all(status == "verified" for status in statuses):
        overall = "evidence_coverage_complete"
    elif "stale" in statuses:
        overall = "evidence_stale_or_incomplete"
    elif "unavailable" in statuses:
        overall = "evidence_unavailable_or_incomplete"
    else:
        overall = "evidence_unverified_or_incomplete"

    return {
        "symbol": str(symbol or "").strip().upper(),
        "assessment_type": "commodity_backing_evidence_review",
        "mode": "read_only",
        "overall_status": overall,
        "not_a_reserve_certification": True,
        "evidence_coverage": coverage,
        "evidence": normalized,
        "invalid_evidence_record_count": sum(1 for item in normalized if item.get("invalid_record")),
        "input_evidence_list_valid": isinstance(evidence, list),
        "freshness_threshold_valid": threshold_valid,
        "freshness_threshold_days": max_age_days,
        "assessment_clock_valid": assessment_clock_valid,
        "limitations": [
            "CIN records evidence metadata; it does not itself audit reserves or certify issuer claims.",
            "A source publication or attestation is not a guarantee of solvency, custody, redemption, or future backing.",
            "Missing evidence is unknown, not proof of backing or lack of backing.",
            "Redemption availability may vary by jurisdiction, customer eligibility, minimum size, fees, and issuer terms.",
        ],
    }
