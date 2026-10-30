"""CIN growth-fundamentals assessment from explicitly supplied evidence (read-only).

Scores are evidence-coverage indicators, not investment recommendations or price forecasts.
CIN does not fetch source documents or independently certify claims in this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any
from urllib.parse import urlsplit

from cin_verifiable_evidence import create_claim, create_claim_evidence_relationship

CATEGORIES = {
    "usage_and_adoption": "On-chain users, transactions, retention, or adoption",
    "fees_and_revenue": "Protocol fees, revenue, or sustainable economic activity",
    "token_utility": "Documented token role, value capture, and necessity",
    "tokenomics_and_unlocks": "Supply schedule, emissions, unlocks, and dilution",
    "security_and_audits": "Audits, incident history, and remediation evidence",
    "developer_activity": "Maintainer activity, releases, and repository evidence",
    "holder_concentration": "Holder concentration, insider allocation, and governance concentration",
    "ecosystem_and_competition": "Ecosystem traction, integrations, and competitive context",
}
VALID_STATUSES = {"verified", "unverified", "stale", "unavailable"}
VALID_SOURCE_ROLES = {"issuer", "custodian", "auditor", "regulator", "exchange", "independent_research", "other"}


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
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


def _timestamp_identity(value: Any) -> str | None:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed is not None else None


def assess_growth_fundamentals(
    symbol: str,
    evidence: list[dict[str, Any]] | None = None,
    *,
    now: datetime | None = None,
    max_age_days: int = 90,
) -> dict[str, Any]:
    """Assess evidence coverage across growth fundamentals; never infer missing facts."""
    threshold_valid = isinstance(max_age_days, int) and not isinstance(max_age_days, bool) and max_age_days >= 0
    max_age_days = max_age_days if threshold_valid else 90
    current, assessment_clock_valid = _assessment_clock(now)

    normalized: list[dict[str, Any]] = []
    source_records = evidence if isinstance(evidence, list) else []
    for item in source_records:
        if not isinstance(item, dict):
            normalized.append({
                "category": "",
                "category_description": "Unknown category",
                "source_name": None,
                "source_url": None,
                "published_at": None,
                "publication_age_days": None,
                "status": "unverified",
                "missing_fields": ["record_object", "recognized_category", "source_name", "source_url", "published_at"],
                "notes": None,
                "cin_independently_verified": False,
                "claim": None,
                "claim_evidence_relationship": None,
                "assessment_clock_valid": assessment_clock_valid,
                "invalid_record": True,
            })
            continue
        kind = str(item.get("category", "")).strip()
        status = str(item.get("status", "unverified")).lower()
        if status not in VALID_STATUSES:
            status = "unverified"
        published = _parse_date(item.get("published_at"))
        checked = _parse_date(item.get("checked_at"))
        source_name = item.get("source_name")
        source_url = item.get("source_url")
        source_url_valid = _is_http_url(source_url)
        raw_evidence_id = item.get("evidence_id")
        evidence_id = raw_evidence_id.strip() if isinstance(raw_evidence_id, str) and 0 < len(raw_evidence_id.strip()) <= 128 else None
        raw_source_role = item.get("source_role")
        source_role = raw_source_role.strip().lower() if isinstance(raw_source_role, str) else None
        if source_role not in VALID_SOURCE_ROLES:
            source_role = "unspecified"
        missing = []
        if kind not in CATEGORIES:
            missing.append("recognized_category")
        if not isinstance(source_name, str) or not source_name.strip():
            missing.append("source_name")
        if not source_url_valid:
            missing.append("source_url")
        if published is None:
            missing.append("published_at")
        if checked is None:
            missing.append("checked_at")
        future_publication = published is not None and published > current
        future_check = checked is not None and checked > current
        check_precedes_publication = published is not None and checked is not None and checked < published
        age = (current - published).days if published is not None and not future_publication else None
        timestamp_validation_errors = []
        if future_publication:
            timestamp_validation_errors.append("published_at_is_in_the_future")
        if future_check:
            timestamp_validation_errors.append("checked_at_is_in_the_future")
        if check_precedes_publication:
            timestamp_validation_errors.append("checked_at_precedes_published_at")
        if timestamp_validation_errors and status == "verified":
            status = "unverified"
        if status == "verified" and missing:
            status = "unverified"
        if status == "verified" and age is not None and age > max_age_days:
            status = "stale"
        record = {
            "category": kind,
            "category_description": CATEGORIES.get(kind, "Unknown category"),
            "evidence_id": evidence_id,
            "evidence_id_is_caller_supplied": evidence_id is not None,
            "source_role": source_role,
            "source_role_is_self_reported": raw_source_role is not None,
            "source_role_authenticated": False,
            "source_name": source_name,
            "source_url": source_url,
            "source_url_valid": source_url_valid,
            "published_at": item.get("published_at"),
            "checked_at": item.get("checked_at"),
            "publication_age_days": age,
            "timestamp_validation_errors": timestamp_validation_errors,
            "assessment_clock_valid": assessment_clock_valid,
            "status": status,
            "missing_fields": missing,
            "claim_text": (item.get("claim_text").strip() or None) if isinstance(item.get("claim_text"), str) else None,
            "claim_text_is_caller_supplied": bool(item.get("claim_text").strip()) if isinstance(item.get("claim_text"), str) else False,
            "notes": str(item.get("notes", "")).strip() or None,
            "cin_independently_verified": False,
            "invalid_record": False,
        }
        claim = None
        relationship = None
        if record["claim_text"]:
            claim = create_claim(
                subject=str(symbol or "").strip().upper(),
                predicate=kind or "unspecified_category",
                statement=record["claim_text"],
                created_at=current,
                claim_status="not_assessed",
            )
            if evidence_id:
                relationship = create_claim_evidence_relationship(
                    claim_id=claim["claim_id"],
                    evidence_id=evidence_id,
                    relationship="context_only",
                    rationale=(
                        "Caller-supplied claim text is linked for traceability only; "
                        "CIN has not independently verified the claim or source."
                    ),
                    review_status="automated_candidate",
                    created_at=current,
                )
        record["claim"] = claim
        record["claim_evidence_relationship"] = relationship
        fingerprint_fields = {key: record.get(key) for key in (
            "category", "evidence_id", "source_role", "source_name", "source_url",
            "published_at", "checked_at", "status", "claim_text", "notes"
        )}
        canonical_payload = json.dumps(fingerprint_fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
        record["record_fingerprint_sha256"] = sha256(canonical_payload).hexdigest()
        record["fingerprint_scope"] = "normalized_supplied_metadata"
        record["fingerprint_is_authenticity_proof"] = False
        normalized.append(record)

    coverage = {}
    for category, description in CATEGORIES.items():
        rows = [row for row in normalized if row["category"] == category]
        distinct_statuses = {row["status"] for row in rows}
        if len(distinct_statuses) > 1:
            status = "conflicting"
        elif distinct_statuses == {"verified"}:
            status = "verified"
        elif distinct_statuses == {"stale"}:
            status = "stale"
        elif distinct_statuses == {"unavailable"}:
            status = "unavailable"
        else:
            status = "unverified"
        identities = {
            (
                row.get("category"),
                _canonical_source_url(row.get("source_url")),
                _timestamp_identity(row.get("published_at")),
            )
            for row in rows
        }
        coverage[category] = {
            "description": description,
            "status": status,
            "evidence_count": len(identities),
            "duplicate_record_count": max(0, len(rows) - len(identities)),
            "conflict_detected": status == "conflicting",
        }

    verified_count = sum(1 for item in coverage.values() if item["status"] == "verified")
    coverage_score = round(100 * verified_count / len(CATEGORIES))
    unrecognized_category_count = sum(
        1 for row in normalized if row["category"] not in CATEGORIES
    )
    invalid_record_count = sum(1 for row in normalized if row.get("invalid_record"))
    if any(item["status"] == "conflicting" for item in coverage.values()):
        overall = "evidence_conflicting_or_incomplete"
    elif unrecognized_category_count or not isinstance(evidence, (list, type(None))):
        overall = "evidence_invalid_or_incomplete"
    elif verified_count == len(CATEGORIES):
        overall = "evidence_coverage_complete"
    elif any(item["status"] == "stale" for item in coverage.values()):
        overall = "evidence_stale_or_incomplete"
    elif any(item["status"] == "unavailable" for item in coverage.values()):
        overall = "evidence_unavailable_or_incomplete"
    else:
        overall = "evidence_unverified_or_incomplete"

    return {
        "symbol": str(symbol or "").strip().upper(),
        "assessment_type": "growth_fundamentals_evidence_review",
        "mode": "read_only",
        "overall_status": overall,
        "evidence_coverage_score": coverage_score,
        "verified_category_count": verified_count,
        "total_category_count": len(CATEGORIES),
        "coverage": coverage,
        "evidence": normalized,
        "unrecognized_category_count": unrecognized_category_count,
        "invalid_evidence_record_count": invalid_record_count,
        "input_evidence_list_valid": isinstance(evidence, (list, type(None))),
        "freshness_threshold_valid": threshold_valid,
        "freshness_threshold_days": max_age_days,
        "assessment_clock_valid": assessment_clock_valid,
        "not_an_investment_recommendation": True,
        "cin_independently_verified_claims": False,
        "limitations": [
            "Coverage score measures supplied evidence metadata coverage only; it is not a project quality score.",
            "CIN does not fetch source documents or independently verify claims in this endpoint.",
            "Source roles and evidence IDs are caller-supplied metadata; roles are unauthenticated and fingerprints detect metadata changes only.",
            "Missing evidence is unknown, not proof of strength, weakness, legitimacy, or fraud.",
            "A source URL or recent publication does not guarantee data accuracy or investment performance.",
            "Token unlock schedules, contract permissions, holder concentration, and on-chain metrics require source-specific review.",
        ],
    }
