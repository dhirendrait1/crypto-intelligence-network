"""Explicit evidence snapshot persistence orchestration.

This helper is opt-in and is not wired into the public API. It never creates a
backend or changes deployment configuration.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from cin_evidence_store import EvidenceStore


def _is_provider_identity_unique_conflict(exc: sqlite3.IntegrityError) -> bool:
    """Recognize only the named provider-identity index violation.

    SQLite exposes a generic UNIQUE error code for every unique constraint.
    Checking the constrained columns prevents an unrelated claim, relationship,
    or primary-key collision from being mistaken for an ingestion race.
    """
    if getattr(exc, "sqlite_errorcode", None) != sqlite3.SQLITE_CONSTRAINT_UNIQUE:
        return False
    message = str(exc)
    return (
        "UNIQUE constraint failed: "
        "cin_evidence_records.source_namespace, "
        "cin_evidence_records.external_evidence_id"
    ) in message


def persist_evidence_snapshot(
    store: EvidenceStore,
    *,
    source_namespace: str,
    external_evidence_id: str,
    evidence_type: str,
    metadata: dict[str, Any],
    observed_at: str,
    claim: dict[str, Any],
    relationship: dict[str, Any],
    source_status: str = "cin_retrieved",
    retrieved_at: str | None = None,
    published_at: str | None = None,
    checked_at: str | None = None,
) -> dict[str, str]:
    """Create the first bundle or append an observation to its existing record.

    A concurrent first-ingestion provider-identity uniqueness conflict is
    resolved by looking up the winning record and appending this retrieval.
    Unrelated integrity failures and all other failures propagate.
    """
    identity = {
        "source_namespace": source_namespace,
        "external_evidence_id": external_evidence_id,
    }
    existing_id = store.find_evidence_id(**identity)
    if existing_id is not None:
        observation_id = store.append_observation(
            cin_evidence_id=existing_id,
            metadata=metadata,
            observed_at=observed_at,
            source_status=source_status,
            retrieved_at=retrieved_at,
            published_at=published_at,
            checked_at=checked_at,
        )
        return {
            "cin_evidence_id": existing_id,
            "observation_id": observation_id,
            "persisted": "true",
            "operation": "observation_appended",
        }

    try:
        result = store.store_bundle(
            **identity,
            evidence_type=evidence_type,
            metadata=metadata,
            observed_at=observed_at,
            claim=claim,
            relationship=relationship,
            source_status=source_status,
            retrieved_at=retrieved_at,
            published_at=published_at,
            checked_at=checked_at,
        )
        return {**result, "operation": "bundle_created"}
    except sqlite3.IntegrityError as exc:
        if not _is_provider_identity_unique_conflict(exc):
            raise
        winning_id = store.find_evidence_id(**identity)
        if winning_id is None:
            raise
        observation_id = store.append_observation(
            cin_evidence_id=winning_id,
            metadata=metadata,
            observed_at=observed_at,
            source_status=source_status,
            retrieved_at=retrieved_at,
            published_at=published_at,
            checked_at=checked_at,
        )
        return {
            "cin_evidence_id": winning_id,
            "observation_id": observation_id,
            "persisted": "true",
            "operation": "observation_appended_after_identity_race",
        }
