"""Pure mapping from successful GitHub connector output to CIN evidence fields.

This module performs no I/O and does not activate API persistence.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from cin_evidence_ingestion import ALLOWED_REPOSITORIES, GITHUB_API_ROOT
from cin_verifiable_evidence import create_claim, create_claim_evidence_relationship


def _aware_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    return parsed


def build_github_evidence_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    """Build opt-in persist_evidence_snapshot kwargs from a successful connector result.

    Failed, malformed, non-allowlisted, or verification-promoted payloads are
    rejected before any EvidenceStore can be called.
    """
    if not isinstance(result, dict):
        raise ValueError("GitHub evidence result must be an object")
    repository = result.get("repository")
    if repository not in ALLOWED_REPOSITORIES:
        raise ValueError("repository is not on CIN's GitHub allowlist")
    if result.get("retrieval_status") != "success":
        raise ValueError("only successful GitHub retrievals can become evidence snapshots")
    if result.get("claim_verification_status") != "unverified" or result.get("independently_verified") is not False:
        raise ValueError("GitHub metadata must remain explicitly unverified")
    if result.get("source_url") != GITHUB_API_ROOT + repository:
        raise ValueError("source_url does not match the canonical GitHub repository")
    retrieved_at = result.get("retrieved_at")
    retrieved_dt = _aware_timestamp(retrieved_at, "retrieved_at")
    published_at = result.get("published_at")
    if published_at is not None:
        _aware_timestamp(published_at, "published_at")

    claim = create_claim(
        subject=repository,
        predicate="public_metadata_snapshot_retrieved",
        statement=f"A public GitHub metadata snapshot was retrieved for {repository} at {retrieved_at}.",
        value={
            "source_name": result.get("source_name"),
            "source_url": result["source_url"],
            "retrieved_at": retrieved_at,
            "validation_status": result.get("validation_status"),
            "freshness_status": result.get("freshness_status"),
            "claim_verification_status": "unverified",
            "independently_verified": False,
        },
        created_at=retrieved_dt,
        claim_status="not_assessed",
    )
    relationship = create_claim_evidence_relationship(
        claim_id=claim["claim_id"],
        evidence_id=repository,
        relationship="context_only",
        rationale=(
            "GitHub repository metadata is contextual source traceability only; "
            "it does not prove ecosystem health, developer quality, adoption, or investment merit."
        ),
        created_at=retrieved_dt,
    )
    snapshot = {
        "source_namespace": "github_public_repository_api",
        "external_evidence_id": repository,
        "evidence_type": "public_repository_metadata_snapshot",
        "metadata": dict(result),
        "observed_at": retrieved_at,
        "retrieved_at": retrieved_at,
        "claim": claim,
        "relationship": relationship,
        "source_status": "cin_retrieved",
    }
    if published_at is not None:
        snapshot["published_at"] = published_at
    return snapshot
