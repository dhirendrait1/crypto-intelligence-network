"""CIN commodity-backed asset evidence assessment (read-only).

This module records evidence metadata; it does not independently certify reserves,
custody, issuer solvency, or redemption rights. Missing evidence is never proof
that backing exists.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any
from urllib.parse import urlsplit

VALID_STATUSES = {"verified", "unverified", "stale", "unavailable"}
VALID_SOURCE_ROLES = {"issuer", "custodian", "auditor", "regulator", "exchange", "independent_research", "other"}
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



def _assessment_clock(now: Any) -> tuple[datetime, bool]:
    """Return a timezone-aware UTC clock and whether the caller supplied a valid one."""
    if now is None:
        return datetime.now(timezone.utc), True
    if not isinstance(now, datetime) or now.tzinfo is None:
        return datetime.now(timezone.utc), False
    try:
        if now.utcoffset() is None:
            return datetime.now(timezone.utc), False
        return now.astimezone(timezone.utc), True
    except (OverflowError, TypeError, ValueError):
        return datetime.now(timezone.utc), False

def _is_http_url(value: Any) -> bool:
    """Accept only absolute HTTP(S) URLs with a hostname and no embedded credentials."""
    if not isinstance(value, str) or any(
        char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value
    ):
        return False
    try:
        parsed = urlsplit(value.strip())
        # Accessing .port validates that a supplied port is numeric and in range.
        parsed.port
        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


def _canonical_source_url(value: Any) -> str:
    """Normalize URL identity without changing case-sensitive path/query content."""
    if not isinstance(value, str):
        return ""
    if not _is_http_url(value):
        return value.strip()
    try:
        parsed = urlsplit(value.strip())
        scheme = parsed.scheme.lower()
        port = parsed.port
        hostname = parsed.hostname.lower()
        host = f"[{hostname}]" if ":" in hostname else hostname
        if port is not None and not (
            (scheme == "https" and port == 443)
            or (scheme == "http" and port == 80)
        ):
            host = f"{host}:{port}"
        path = parsed.path.rstrip("/") or "/"
        return scheme + "://" + host + path + (f"?{parsed.query}" if parsed.query else "")
    except ValueError:
        return value.strip()



def _source_host(value: Any) -> str | None:
    """Return normalized hostname for source-diversity diagnostics only."""
    if not _is_http_url(value):
        return None
    try:
        return (urlsplit(value.strip()).hostname or "").lower() or None
    except ValueError:
        return None


def _timestamp_identity(value: Any) -> str | None:
    parsed = _parse_timestamp(value)
    return parsed.isoformat() if parsed is not None else None


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
    current, assessment_clock_valid = _assessment_clock(now)

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
            "source_host": None,
            "freshness_threshold_days": max_age_days,
            "assessment_clock_valid": assessment_clock_valid,
            "invalid_record": True,
        }

    record = {field: item.get(field) for field in REQUIRED_EVIDENCE_FIELDS}
    raw_evidence_id = item.get("evidence_id")
    record["evidence_id"] = raw_evidence_id.strip() if isinstance(raw_evidence_id, str) and 0 < len(raw_evidence_id.strip()) <= 128 else None
    record["evidence_id_is_caller_supplied"] = record["evidence_id"] is not None
    raw_source_role = item.get("source_role")
    normalized_source_role = raw_source_role.strip().lower() if isinstance(raw_source_role, str) else None
    if normalized_source_role not in VALID_SOURCE_ROLES:
        normalized_source_role = "unspecified"
    record["source_role"] = normalized_source_role
    record["source_role_is_self_reported"] = raw_source_role is not None
    record["source_role_authenticated"] = False
    record["claim_text"] = str(item.get("claim_text", "")).strip() or None
    record["claim_text_is_caller_supplied"] = record["claim_text"] is not None
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
    record["source_host"] = _source_host(record.get("source_url"))
    record["publication_age_days"] = age_days
    record["missing_fields"] = missing
    record["timestamp_validation_errors"] = timestamp_errors
    record["source_url_valid"] = url_valid
    record["freshness_threshold_days"] = max_age_days
    record["assessment_clock_valid"] = assessment_clock_valid
    fingerprint_fields = {
        field: record.get(field)
        for field in (*REQUIRED_EVIDENCE_FIELDS, "evidence_id", "source_role", "claim_text", "notes")
    }
    canonical_payload = json.dumps(
        fingerprint_fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    record["record_fingerprint_sha256"] = sha256(canonical_payload).hexdigest()
    record["fingerprint_scope"] = "normalized_supplied_metadata"
    record["fingerprint_is_authenticity_proof"] = False
    return record


def compare_evidence_snapshots(previous: list[dict[str, Any]], current: list[dict[str, Any]], *, now: datetime | None = None, max_age_days: int = 90) -> dict[str, Any]:
    """Compare caller-supplied snapshots by stable evidence_id; persist nothing."""
    if not isinstance(previous, list) or not isinstance(current, list):
        raise ValueError("previous and current snapshots must both be lists")

    def index_snapshot(items):
        indexed = {}
        duplicates = set()
        untracked = 0
        for item in items:
            normalized = normalize_evidence(item, now=now, max_age_days=max_age_days)
            evidence_id = normalized.get("evidence_id")
            if not evidence_id:
                untracked += 1
                continue
            if evidence_id in indexed:
                duplicates.add(evidence_id)
                indexed.pop(evidence_id, None)
                continue
            if evidence_id not in duplicates:
                indexed[evidence_id] = normalized
        return indexed, duplicates, untracked

    previous_index, previous_duplicates, previous_untracked = index_snapshot(previous)
    current_index, current_duplicates, current_untracked = index_snapshot(current)
    ambiguous_ids = sorted(previous_duplicates | current_duplicates)
    changes = []
    for evidence_id in sorted((set(previous_index) | set(current_index)) - set(ambiguous_ids)):
        before = previous_index.get(evidence_id)
        after = current_index.get(evidence_id)
        if before is None:
            change_type = "added"
        elif after is None:
            change_type = "removed"
        elif before.get("record_fingerprint_sha256") != after.get("record_fingerprint_sha256"):
            change_type = "changed"
        else:
            change_type = "unchanged"
        changes.append({
            "evidence_id": evidence_id,
            "change_type": change_type,
            "previous_fingerprint_sha256": before.get("record_fingerprint_sha256") if before else None,
            "current_fingerprint_sha256": after.get("record_fingerprint_sha256") if after else None,
        })

    return {
        "comparison_mode": "caller_supplied_snapshots",
        "history_persisted": False,
        "change_count": len(changes),
        "counts": {kind: sum(1 for item in changes if item["change_type"] == kind) for kind in ("added", "removed", "changed", "unchanged")},
        "changes": changes,
        "ambiguous_evidence_ids": ambiguous_ids,
        "untracked_previous_record_count": previous_untracked,
        "untracked_current_record_count": current_untracked,
        "limitations": [
            "CIN compares only snapshots supplied in this request; no history is stored.",
            "Stable evidence_id values are caller-supplied and are not authenticated by CIN.",
            "Fingerprints cover normalized metadata, not source-document contents or authenticity.",
            "Ambiguous duplicate IDs are excluded from change classification.",
        ],
    }

def assess_commodity_asset(symbol: str, evidence: list[dict[str, Any]], *,
                           now: datetime | None = None,
                           max_age_days: int = 90) -> dict[str, Any]:
    """Summarize reserve/redemption/custody evidence without treating gaps as proof."""
    threshold_valid = isinstance(max_age_days, int) and not isinstance(max_age_days, bool) and max_age_days >= 0
    max_age_days = max_age_days if threshold_valid else 90
    current, assessment_clock_valid = _assessment_clock(now)
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
                _canonical_source_url(record.get("source_url")),
                _timestamp_identity(record.get("published_at")),
                _timestamp_identity(record.get("checked_at")),
            )
            for record in records
        }
        source_hosts = sorted({record.get("source_host") for record in records if record.get("source_host")})
        role_counts = {role: sum(1 for record in records if record.get("source_role") == role) for role in sorted(VALID_SOURCE_ROLES | {"unspecified"})}
        status_counts = {status: sum(1 for record in records if record.get("status") == status) for status in sorted(VALID_STATUSES)}
        conflict_evidence = []
        if state == "conflicting":
            conflict_evidence = [
                {
                    "status": record.get("status"),
                    "source_role": record.get("source_role", "unspecified"),
                    "source_role_authenticated": False,
                    "source_name": record.get("source_name"),
                    "source_url": record.get("source_url"),
                }
                for record in records
            ]
        coverage[kind] = {
            "status": state,
            "evidence_count": len(identities),
            "duplicate_record_count": max(0, len(records) - len(identities)),
            "conflict_detected": state == "conflicting",
            "distinct_source_host_count": len(source_hosts),
            "source_host_diversity": (
                "multiple_hosts" if len(source_hosts) > 1
                else "single_host" if source_hosts
                else "no_valid_hosts"
            ),
            "source_independence_verified": False,
            "source_role_counts_self_reported": role_counts,
            "source_roles_authenticated": False,
            "status_counts": status_counts,
            "conflict_evidence": conflict_evidence,
            "conflict_resolution": "manual_review_required" if state == "conflicting" else "not_applicable",
            "preferred_source_selected": False,
        }

    statuses = [value["status"] for value in coverage.values()]
    unrecognized_evidence_type_count = sum(
        1 for row in normalized if row.get("evidence_type") not in required_types
    )
    invalid_evidence_record_count = sum(1 for row in normalized if row.get("invalid_record"))
    if "conflicting" in statuses:
        overall = "evidence_conflicting_or_incomplete"
    elif (
        unrecognized_evidence_type_count
        or invalid_evidence_record_count
        or not isinstance(evidence, list)
    ):
        overall = "evidence_invalid_or_incomplete"
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
        "invalid_evidence_record_count": invalid_evidence_record_count,
        "unrecognized_evidence_type_count": unrecognized_evidence_type_count,
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
