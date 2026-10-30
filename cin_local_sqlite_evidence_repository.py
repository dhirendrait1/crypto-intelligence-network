"""Explicit local SQLite repository for CIN claim/evidence development tests.

This adapter is not imported by the API, does not initialize itself, and is not
suitable as production storage on an ephemeral filesystem/service.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3
from typing import Any
from uuid import uuid4


def _utc_timestamp(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class LocalSQLiteEvidenceRepository:
    """Small explicit-connection adapter; callers own connection and migration."""

    def __init__(self, connection: sqlite3.Connection):
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError("connection must be sqlite3.Connection")
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")


    def append_assessment_event(
        self,
        *,
        claim_id: str,
        claim_status: str,
        assessed_at: str,
        methodology_version: str,
        assessor_type: str,
        rationale: str,
    ) -> str:
        """Append a new assessment; never overwrite an earlier assessment."""
        allowed_statuses = {
            "supported", "contradicted", "mixed",
            "insufficient_evidence", "not_assessed",
        }
        if claim_status not in allowed_statuses:
            raise ValueError("unsupported claim_status")
        if assessor_type not in {"automated_rule", "human_reviewer"}:
            raise ValueError("unsupported assessor_type")
        if not isinstance(claim_id, str) or not claim_id.strip():
            raise ValueError("claim_id must be non-empty")
        if not isinstance(methodology_version, str) or not methodology_version.strip():
            raise ValueError("methodology_version must be non-empty")
        if not isinstance(rationale, str) or not rationale.strip() or len(rationale.strip()) > 4000:
            raise ValueError("rationale must contain 1..4000 characters")
        timestamp = _utc_timestamp(assessed_at, "assessed_at")
        event_id = "cin-assessment-" + uuid4().hex
        with self.connection:
            self.connection.execute(
                """INSERT INTO cin_claim_assessment_events
                   (assessment_event_id, claim_id, claim_status, assessed_at,
                    methodology_version, assessor_type, rationale)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (event_id, claim_id, claim_status, timestamp,
                 methodology_version.strip(), assessor_type, rationale.strip()),
            )
        return event_id

    def append_observation(
        self,
        *,
        cin_evidence_id: str,
        metadata: dict[str, Any],
        observed_at: str,
        source_status: str,
        retrieved_at: str | None = None,
        published_at: str | None = None,
        checked_at: str | None = None,
    ) -> str:
        """Append an immutable observation to an existing CIN evidence record."""
        if not isinstance(cin_evidence_id, str) or not cin_evidence_id.strip():
            raise ValueError("cin_evidence_id must be non-empty")
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a JSON object")
        if source_status not in {"caller_supplied", "cin_observed", "cin_retrieved", "unavailable", "invalid"}:
            raise ValueError("unsupported source_status")
        observed = _utc_timestamp(observed_at, "observed_at")
        retrieved = _utc_timestamp(retrieved_at, "retrieved_at") if retrieved_at is not None else None
        published = _utc_timestamp(published_at, "published_at") if published_at is not None else None
        checked = _utc_timestamp(checked_at, "checked_at") if checked_at is not None else None
        metadata_json = json.dumps(
            metadata, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        fingerprint = sha256(metadata_json.encode("utf-8")).hexdigest()
        observation_id = "cin-observation-" + uuid4().hex
        with self.connection:
            self.connection.execute(
                """INSERT INTO cin_evidence_observations
                   (observation_id, cin_evidence_id, observed_at, retrieved_at, published_at,
                    checked_at, metadata_json, metadata_fingerprint_sha256,
                    content_hash_sha256, source_status, schema_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)""",
                (observation_id, cin_evidence_id, observed, retrieved, published,
                 checked, metadata_json, fingerprint, source_status, "1.0"),
            )
        return observation_id

    def store_bundle(
        self,
        *,
        source_namespace: str,
        evidence_type: str,
        metadata: dict[str, Any],
        observed_at: str,
        claim: dict[str, Any],
        relationship: dict[str, Any],
        external_evidence_id: str | None = None,
        published_at: str | None = None,
        checked_at: str | None = None,
        retrieved_at: str | None = None,
        source_status: str = "caller_supplied",
    ) -> dict[str, str]:
        """Atomically persist one evidence observation, claim and relationship.

        Caller-supplied metadata is not treated as retrieved/authenticated source
        material. No URLs are fetched and no claim status is inferred here.
        """
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a JSON object")
        if not isinstance(source_namespace, str) or not source_namespace.strip() or len(source_namespace.strip()) > 128:
            raise ValueError("source_namespace must contain 1..128 characters")
        if not isinstance(evidence_type, str) or not evidence_type.strip() or len(evidence_type.strip()) > 128:
            raise ValueError("evidence_type must contain 1..128 characters")
        if external_evidence_id is not None and (
            not isinstance(external_evidence_id, str) or not external_evidence_id.strip()
            or len(external_evidence_id.strip()) > 256
        ):
            raise ValueError("external_evidence_id must contain 1..256 characters")
        if source_status not in {"caller_supplied", "cin_observed", "cin_retrieved", "unavailable", "invalid"}:
            raise ValueError("unsupported source_status")

        observed = _utc_timestamp(observed_at, "observed_at")
        retrieved = _utc_timestamp(retrieved_at, "retrieved_at") if retrieved_at is not None else None
        published = _utc_timestamp(published_at, "published_at") if published_at is not None else None
        checked = _utc_timestamp(checked_at, "checked_at") if checked_at is not None else None

        required_claim = ("claim_id", "subject", "predicate", "statement", "created_at", "schema_version", "identifier_method")
        if not isinstance(claim, dict) or any(k not in claim for k in required_claim):
            raise ValueError("claim is missing required identity fields")
        if claim.get("claim_status") not in {"supported", "contradicted", "mixed", "insufficient_evidence", "not_assessed"}:
            raise ValueError("claim has unsupported status")
        claim_created = _utc_timestamp(claim["created_at"], "claim.created_at")
        value_json = json.dumps(claim.get("value"), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) if claim.get("value") is not None else None

        required_rel = ("claim_id", "relationship", "review_status", "rationale", "created_at", "schema_version")
        if not isinstance(relationship, dict) or any(k not in relationship for k in required_rel):
            raise ValueError("relationship is missing required fields")
        if relationship["claim_id"] != claim["claim_id"]:
            raise ValueError("relationship claim_id must match claim")
        if relationship.get("relationship") not in {"supports", "contradicts", "qualifies", "context_only"}:
            raise ValueError("unsupported relationship type")
        if relationship.get("review_status") not in {"automated_candidate", "human_reviewed", "rejected"}:
            raise ValueError("unsupported relationship review status")
        relationship_created = _utc_timestamp(relationship["created_at"], "relationship.created_at")

        metadata_json = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        fingerprint = sha256(metadata_json.encode("utf-8")).hexdigest()
        cin_evidence_id = "cin-evidence-" + uuid4().hex
        observation_id = "cin-observation-" + uuid4().hex
        relationship_id = "cin-relationship-" + uuid4().hex
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        with self.connection:
            self.connection.execute(
                """INSERT INTO cin_evidence_records
                   (cin_evidence_id, source_namespace, external_evidence_id, evidence_type, created_at, schema_version)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cin_evidence_id, source_namespace.strip(), external_evidence_id.strip() if external_evidence_id else None,
                 evidence_type.strip(), now, "1.0"),
            )
            self.connection.execute(
                """INSERT INTO cin_evidence_observations
                   (observation_id, cin_evidence_id, observed_at, retrieved_at, published_at, checked_at,
                    metadata_json, metadata_fingerprint_sha256, content_hash_sha256, source_status, schema_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)""",
                (observation_id, cin_evidence_id, observed, retrieved, published, checked,
                 metadata_json, fingerprint, source_status, "1.0"),
            )
            self.connection.execute(
                """INSERT INTO cin_claims
                   (claim_id, subject, predicate, statement, value_json, unit, valid_time_start, valid_time_end,
                    created_at, schema_version, identifier_method)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (claim["claim_id"], claim["subject"], claim["predicate"], claim["statement"], value_json,
                 claim.get("unit"), claim.get("valid_time_start"), claim.get("valid_time_end"),
                 claim_created, claim["schema_version"], claim["identifier_method"]),
            )
            self.connection.execute(
                """INSERT INTO cin_claim_assessment_events
                   (assessment_event_id, claim_id, claim_status, assessed_at, methodology_version, assessor_type, rationale)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("cin-assessment-" + uuid4().hex, claim["claim_id"], claim["claim_status"],
                 claim_created, "initial-unassessed-v1", "automated_rule",
                 "Initial claim status supplied by the claim builder; no truth inference."),
            )
            self.connection.execute(
                """INSERT INTO cin_claim_evidence_relationships
                   (relationship_id, claim_id, cin_evidence_id, relationship_type, review_status, rationale, created_at, schema_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (relationship_id, claim["claim_id"], cin_evidence_id, relationship["relationship"],
                 relationship["review_status"], relationship["rationale"], relationship_created,
                 relationship["schema_version"]),
            )

        return {
            "cin_evidence_id": cin_evidence_id,
            "observation_id": observation_id,
            "claim_id": claim["claim_id"],
            "relationship_id": relationship_id,
            "persisted": "true",
            "storage_mode": "local_sqlite_development_only",
        }
