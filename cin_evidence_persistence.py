"""Explicit evidence snapshot persistence orchestration.

This helper is opt-in and is not wired into the public API. It never creates a
backend or changes deployment configuration.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from cin_evidence_store import EvidenceStore


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

    A concurrent first-ingestion uniqueness conflict is resolved by looking up
    the winning record and appending this retrieval as a new observation.
    Non-integrity failures propagate; they are never reported as persistence
    success.
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
    except sqlite3.IntegrityError:
        # A concurrent first-ingestion may have won the unique identity race.
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
