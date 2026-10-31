"""Storage contract for CIN's local/development evidence persistence adapters.

The protocol defines an application-facing boundary only. It performs no I/O,
selects no backend, and does not imply that a durable production store is ready.
"""
from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class EvidenceStore(Protocol):
    """Structural contract for append-oriented CIN evidence persistence."""

    def find_evidence_id(
        self,
        *,
        source_namespace: str,
        external_evidence_id: str,
    ) -> str | None:
        """Return the existing evidence ID for a provider identity, or None."""
        ...

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
        """Atomically add one evidence record, first observation, claim and link."""
        ...

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
        """Append a new immutable observation to an existing evidence record."""
        ...

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
        """Append a versioned assessment event; never overwrite prior history."""
        ...
