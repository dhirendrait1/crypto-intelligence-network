"""CIN growth-fundamentals assessment from explicitly supplied evidence (read-only).

Scores are evidence-coverage indicators, not investment recommendations or price forecasts.
CIN does not fetch source documents or independently certify claims in this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def assess_growth_fundamentals(
    symbol: str,
    evidence: list[dict[str, Any]] | None = None,
    *,
    now: datetime | None = None,
    max_age_days: int = 90,
) -> dict[str, Any]:
    """Assess evidence coverage across growth fundamentals; never infer missing facts."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)

    normalized: list[dict[str, Any]] = []
    for item in evidence or []:
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
        if not isinstance(source_url, str) or not source_url.startswith(("https://", "http://")):
            missing.append("source_url")
        if published is None:
            missing.append("published_at")
        age = max(0, (current - published).days) if published else None
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
            "status": status,
            "missing_fields": missing,
            "notes": str(item.get("notes", "")).strip() or None,
            "cin_independently_verified": False,
        })

    coverage = {}
    for category, description in CATEGORIES.items():
        rows = [row for row in normalized if row["category"] == category]
        if any(row["status"] == "verified" for row in rows):
            status = "verified"
        elif any(row["status"] == "stale" for row in rows):
            status = "stale"
        elif any(row["status"] == "unavailable" for row in rows):
            status = "unavailable"
        else:
            status = "unverified"
        coverage[category] = {
            "description": description,
            "status": status,
            "evidence_count": len(rows),
        }

    verified_count = sum(1 for item in coverage.values() if item["status"] == "verified")
    coverage_score = round(100 * verified_count / len(CATEGORIES))
    if verified_count == len(CATEGORIES):
        overall = "evidence_coverage_complete"
    elif any(item["status"] == "stale" for item in coverage.values()):
        overall = "evidence_stale_or_incomplete"
    elif any(item["status"] == "unavailable" for item in coverage.values()):
        overall = "evidence_unavailable_or_incomplete"
    else:
        overall = "evidence_unverified_or_incomplete"

    return {
        "symbol": symbol.strip().upper(),
        "assessment_type": "growth_fundamentals_evidence_review",
        "mode": "read_only",
        "overall_status": overall,
        "evidence_coverage_score": coverage_score,
        "verified_category_count": verified_count,
        "total_category_count": len(CATEGORIES),
        "coverage": coverage,
        "evidence": normalized,
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
