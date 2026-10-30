"""Shared CIN claim/evidence objects (read-only; no persistence or source verification)."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

CLAIM_STATUSES = {
    "supported", "contradicted", "mixed", "insufficient_evidence", "not_assessed"
}
RELATIONSHIPS = {"supports", "contradicts", "qualifies", "context_only"}
REVIEW_STATUSES = {"automated_candidate", "human_reviewed", "rejected"}
SCHEMA_VERSION = "1.0"


def _aware_iso(value: Any, field: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")
    try:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a valid timezone-aware datetime") from exc


def _required_text(value: Any, field: str, limit: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > limit:
        raise ValueError(f"{field} must be at most {limit} characters")
    return normalized


def create_claim(
    *, subject: str, predicate: str, statement: str,
    value: Any = None, unit: str | None = None,
    valid_time_start: datetime | None = None,
    valid_time_end: datetime | None = None,
    created_at: datetime | None = None,
    claim_status: str = "not_assessed",
) -> dict[str, Any]:
    """Build a deterministic claim object; edits to identity fields yield a new ID.

    The identifier is a content-derived stable key, not proof that the claim is true.
    """
    subject_value = _required_text(subject, "subject", 512)
    predicate_value = _required_text(predicate, "predicate", 128).lower()
    statement_value = _required_text(statement, "statement", 4000)
    if claim_status not in CLAIM_STATUSES:
        raise ValueError("claim_status is not a supported CIN claim status")
    unit_value = None if unit is None else _required_text(unit, "unit", 64)
    start = _aware_iso(valid_time_start, "valid_time_start") if valid_time_start is not None else None
    end = _aware_iso(valid_time_end, "valid_time_end") if valid_time_end is not None else None
    if start and end and datetime.fromisoformat(start.replace("Z", "+00:00")) > datetime.fromisoformat(end.replace("Z", "+00:00")):
        raise ValueError("valid_time_start must not be after valid_time_end")
    identity = {
        "subject": subject_value,
        "predicate": predicate_value,
        "statement": statement_value,
        "value": value,
        "unit": unit_value,
        "valid_time_start": start,
        "valid_time_end": end,
    }
    try:
        identity_json = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("value must be JSON-serializable and finite") from exc
    claim_id = "cin-claim-" + sha256(identity_json.encode("utf-8")).hexdigest()[:32]
    created = _aware_iso(created_at or datetime.now(timezone.utc), "created_at")
    return {
        "claim_id": claim_id,
        **identity,
        "created_at": created,
        "claim_status": claim_status,
        "schema_version": SCHEMA_VERSION,
        "identifier_method": "sha256_canonical_claim_identity_v1",
        "claim_id_is_truth_proof": False,
    }


def create_claim_evidence_relationship(
    *, claim_id: str, evidence_id: str, relationship: str,
    rationale: str, review_status: str = "automated_candidate",
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a validated link between existing claim/evidence IDs; stores nothing."""
    claim = _required_text(claim_id, "claim_id", 128)
    evidence = _required_text(evidence_id, "evidence_id", 128)
    reason = _required_text(rationale, "rationale", 2000)
    if relationship not in RELATIONSHIPS:
        raise ValueError("relationship must be supports, contradicts, qualifies, or context_only")
    if review_status not in REVIEW_STATUSES:
        raise ValueError("review_status is not a supported CIN review status")
    return {
        "claim_id": claim,
        "evidence_id": evidence,
        "relationship": relationship,
        "rationale": reason,
        "review_status": review_status,
        "created_at": _aware_iso(created_at or datetime.now(timezone.utc), "created_at"),
        "schema_version": SCHEMA_VERSION,
        "relationship_is_persisted": False,
    }
