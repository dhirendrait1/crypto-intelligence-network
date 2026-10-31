# CIN Step 23 — GitHub Evidence Mapping v1

**Status:** Pure mapping contract implemented and tested. Persistence remains explicit opt-in; public API writes remain disabled.

## Mapping contract

`map_github_snapshot_to_evidence_fields(snapshot)` accepts only a successful result from the allowlisted GitHub metadata connector that explicitly remains unverified. It returns arguments for the existing `EvidenceStore` orchestration helper; it performs no I/O and does not call the store.

- Identity: fixed namespace `github_public_repository_api` plus canonical allowlisted repository name.
- Type: `public_repository_metadata_snapshot`.
- Metadata: the complete normalized connector result, including provenance, freshness, validation, missing fields and limitations.
- Observation and retrieval times: connector `retrieved_at`.
- Provider timestamp: timezone-aware `published_at`, when present; no `checked_at` is asserted.
- Source status: `cin_retrieved` only for a successful retrieval.
- Claim: narrow `public_metadata_snapshot_retrieved`, status `not_assessed`.
- Relationship: `context_only`, `automated_candidate`; explicitly not proof of quality, adoption or investment merit.

Failed retrievals, non-canonical repositories, verified/promoted claims and invalid timestamps are rejected before persistence can be called.

## Validation and rollout boundary

Mapping tests cover full-payload preservation, provenance timestamp normalization, strict failure rejection, and compatibility with the actual connector output shape. Existing SQLite integration tests separately cover first/repeat ingestion, append-only observations, provenance persistence and concurrent identity races.

This mapper is not wired into `cin_evidence_ingestion_api.py`. SQLite remains a local development/test adapter. No automatic initialization, production backend, deployment, paid service, trading, wallet or fund-movement capability is introduced.
