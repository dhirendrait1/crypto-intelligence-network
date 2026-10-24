"""CIN growth-fundamentals assessment from explicitly supplied evidence (read-only).

Scores are evidence-coverage indicators, not investment recommendations or price forecasts.
CIN does not fetch source documents or independently certify claims in this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

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



def _is_http_url(value: Any) -> bool:
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
                "invalid_record": True,
            })
            continue
        kind = str(item.get("category", "")).strip()
        status = str(item.get("status", "unverified")).lower()
        if status not in VALID_STATUSES:
            status = "unverified"
        published = _parse_date(item.get("published_at"))
        source_name = item.get("source_name")
        source_url = item.get("source_url")
        missing = []
        if kind not in CATEGORIES:
            missing.append("recognized_category")
        if not isinstance(source_name, str) or not source_name.strip():
            missing.append("source_name")
        if not _is_http_url(source_url):
            missing.append("source_url")
        if published is None:
            missing.append("published_at")
        future_publication = published is not None and published > current
        age = (current - published).days if published is not None and not future_publication else None
        timestamp_validation_errors = ["published_at_is_in_the_future"] if future_publication else []
        if future_publication and status == "verified":
            status = "unverified"
        if status == "verified" and missing:
            status = "unverified"
        if status == "verified" and age is not None and age > max_age_days:
            status = "stale"
        normalized.append({
            "category": kind,
            "category_description": CATEGORIES.get(kind, "Unknown category"),
            "source_name": source_name,
            "source_url": source_url,
            "published_at": item.get("published_at"),
            "publication_age_days": age,
            "timestamp_validation_errors": timestamp_validation_errors,
            "status": status,
            "missing_fields": missing,
            "notes": str(item.get("notes", "")).strip() or None,
            "cin_independently_verified": False,
            "invalid_record": False,
        })

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
                str(row.get("source_url") or "").strip().rstrip("/").lower(),
                row.get("published_at"),
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
            "Missing evidence is unknown, not proof of strength, weakness, legitimacy, or fraud.",
            "A source URL or recent publication does not guarantee data accuracy or investment performance.",
            "Token unlock schedules, contract permissions, holder concentration, and on-chain metrics require source-specific review.",
        ],
    }
