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
import re

MAX_TEXT_LENGTHS = {
    "subject": 512,
    "predicate": 128,
    "statement": 4000,
    "unit": 64,
    "identifier_method": 128,
    "methodology_version": 128,
    "relationship.rationale": 2000,
    "assessment.rationale": 4000,
}
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"\b(?:sk_live|sk_test|gh[pousr]_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{12,}", re.IGNORECASE),
    re.compile(r"\b(?:api[_ -]?key|access[_ -]?token|secret[_ -]?key|private[_ -]?key|recovery[_ -]?phrase|seed[_ -]?phrase|mnemonic)\s*[:=]\s*\S+", re.IGNORECASE),
)

def _validate_text(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > limit:
        raise ValueError(f"{field} must be at most {limit} characters")
    if any(pattern.search(normalized) for pattern in _SECRET_PATTERNS):
        raise ValueError(f"{field} contains a prohibited credential or secret marker")
    return normalized

def _validate_claim_value(value: Any) -> None:
    secret_keys = {"password", "passwd", "token", "access_token", "api_key",
                   "secret", "secret_key", "private_key", "seed_phrase",
                   "mnemonic", "authorization", "cookie"}
    def walk(item: Any, depth: int = 0) -> None:
        if depth > MAX_METADATA_DEPTH:
            raise ValueError("claim value exceeds the maximum nesting depth")
        if isinstance(item, dict):
            for key, child in item.items():
                if isinstance(key, str) and key.strip().lower() in secret_keys:
                    raise ValueError("claim value contains a prohibited sensitive field")
                walk(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                walk(child, depth + 1)
        elif isinstance(item, str):
            if any(pattern.search(item) for pattern in _SECRET_PATTERNS):
                raise ValueError("claim value contains a prohibited credential or secret marker")

MAX_METADATA_BYTES = 64 * 1024
MAX_METADATA_DEPTH = 8
MAX_METADATA_NODES = 2048
MAX_METADATA_STRING_CHARS = 8192
MAX_METADATA_COLLECTION_ITEMS = 256

# Exact source schema for the only connector currently approved for evidence
# mapping. Other namespaces receive structural/size validation but no claim of
# source authenticity or semantic approval.
SOURCE_METADATA_ALLOWLISTS = {
    "github_public_repository_api": {
        "symbol", "category", "metric", "source_name", "source_url",
        "repository", "published_at", "retrieved_at", "measurement_period",
        "value", "unit", "retrieval_status", "validation_status",
        "missing_fields", "freshness_status", "freshness_age_seconds",
        "freshness_policy", "claim_verification_status",
        "independently_verified", "provenance", "limitations",
    }
}
GITHUB_VALUE_ALLOWLIST = {
    "default_branch", "pushed_at", "updated_at", "stargazers_count",
    "forks_count", "open_issues_count", "archived",
}


def _serialize_metadata(metadata: dict[str, Any], source_namespace: str) -> str:
    """Validate source shape and resource bounds before canonical JSON encoding."""
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a JSON object")

    allowed = SOURCE_METADATA_ALLOWLISTS.get(source_namespace)
    if allowed is not None:
        unknown = set(metadata) - allowed
        if unknown:
            raise ValueError("metadata contains fields outside the source allowlist")
        nested_value = metadata.get("value")
        if nested_value is not None:
            if not isinstance(nested_value, dict) or set(nested_value) - GITHUB_VALUE_ALLOWLIST:
                raise ValueError("metadata value contains fields outside the source allowlist")

    nodes = 0

    def inspect(value: Any, depth: int = 0) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_METADATA_NODES:
            raise ValueError("metadata exceeds the maximum JSON node count")
        if depth > MAX_METADATA_DEPTH:
            raise ValueError("metadata exceeds the maximum JSON nesting depth")
        if isinstance(value, str):
            if len(value) > MAX_METADATA_STRING_CHARS:
                raise ValueError("metadata string exceeds the maximum length")
        elif isinstance(value, dict):
            if len(value) > MAX_METADATA_COLLECTION_ITEMS:
                raise ValueError("metadata object exceeds the maximum field count")
            for key, child in value.items():
                if not isinstance(key, str) or len(key) > 128:
                    raise ValueError("metadata object keys must be strings of at most 128 characters")
                inspect(child, depth + 1)
        elif isinstance(value, list):
            if len(value) > MAX_METADATA_COLLECTION_ITEMS:
                raise ValueError("metadata array exceeds the maximum item count")
            for child in value:
                inspect(child, depth + 1)
        elif value is None or isinstance(value, (bool, int, float)):
            return
        else:
            raise ValueError("metadata contains an unsupported JSON value")

    inspect(metadata)
    try:
        encoded = json.dumps(
            metadata, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("metadata must contain finite JSON-compatible values") from exc
    if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
        raise ValueError("metadata exceeds the 65536-byte storage limit")
    return encoded


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


    def find_evidence_id(
        self,
        *,
        source_namespace: str,
        external_evidence_id: str,
    ) -> str | None:
        """Read an existing evidence ID by its unique provider identity."""
        if (
            not isinstance(source_namespace, str)
            or not source_namespace.strip()
            or len(source_namespace.strip()) > 128
        ):
            raise ValueError("source_namespace must contain 1..128 characters")
        if (
            not isinstance(external_evidence_id, str)
            or not external_evidence_id.strip()
            or len(external_evidence_id.strip()) > 256
        ):
            raise ValueError("external_evidence_id must contain 1..256 characters")
        row = self.connection.execute(
            """SELECT cin_evidence_id
               FROM cin_evidence_records
               WHERE source_namespace = ? AND external_evidence_id = ?""",
            (source_namespace.strip(), external_evidence_id.strip()),
        ).fetchone()
        return row["cin_evidence_id"] if row is not None else None

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
        methodology_version = _validate_text(methodology_version, "methodology_version", MAX_TEXT_LENGTHS["methodology_version"])
        rationale = _validate_text(rationale, "assessment.rationale", MAX_TEXT_LENGTHS["assessment.rationale"])
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
        namespace_row = self.connection.execute(
            "SELECT source_namespace FROM cin_evidence_records WHERE cin_evidence_id = ?",
            (cin_evidence_id,),
        ).fetchone()
        if namespace_row is None:
            # Preserve the database FK as the authoritative unknown-record error.
            source_namespace = ""
        else:
            source_namespace = namespace_row["source_namespace"]
        metadata_json = _serialize_metadata(metadata, source_namespace)
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
        for field in ("subject", "predicate", "statement", "identifier_method"):
            claim[field] = _validate_text(claim[field], f"claim.{field}", MAX_TEXT_LENGTHS[field])
        if claim.get("unit") is not None:
            claim["unit"] = _validate_text(claim["unit"], "claim.unit", MAX_TEXT_LENGTHS["unit"])
        if claim.get("value") is not None:
            _validate_claim_value(claim["value"])
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
        relationship["rationale"] = _validate_text(
            relationship["rationale"], "relationship.rationale",
            MAX_TEXT_LENGTHS["relationship.rationale"],
        )

        metadata_json = _serialize_metadata(metadata, source_namespace.strip())
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
