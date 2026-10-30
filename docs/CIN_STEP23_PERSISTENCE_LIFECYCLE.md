# CIN Step 23 — Persistence and Evidence Lifecycle Design

**Status:** Design only; no database, migration, repository, retention job, or public endpoint is implemented by this document.  
**Schema baseline:** shared claim/evidence schema v1.0 (cin_verifiable_evidence.py).  
**Safety boundary:** read-only intelligence. This design does not authorize source crawling, account access, trading, wallet access, or fund movement.

## 1. Design decisions

1. Keep claims, evidence records, and claim-evidence relationships as separate entities. Their identifiers and lifecycles must not be conflated.
2. Treat caller-provided evidence IDs as external identifiers, not globally trusted primary keys. Assign a CIN-owned immutable evidence-record ID at ingestion and retain the caller ID in a separate namespaced field.
3. Persist source observations as time-bounded snapshots. A changed source record creates a new observation/version; it must not silently overwrite the prior observation.
4. Keep claim identity independent from assessment state. The content-derived claim ID remains stable for the same canonical identity; status changes are recorded as separate assessment events, not by changing the claim ID.
5. Keep relationship evidence conservative. Current commodity/growth integrations create only context_only + automated_candidate; never promote these automatically to supports, contradicts, or human_reviewed.
6. Store source metadata and bounded extracted text only when legally permitted and explicitly configured. Default to metadata-only; do not mirror full source documents.
7. Make retention, deletion, licensing, privacy, and provider authorization explicit gates before enabling persistence or scheduled collection.

## 2. Logical entities and required fields

| Entity | Required fields | Purpose |
|---|---|---|
| evidence_record | cin_evidence_id (CIN UUID/ULID), source_namespace, external_evidence_id (nullable), evidence_type, created_at, schema_version | Stable CIN-owned identity for an evidence item |
| evidence_observation | observation_id, cin_evidence_id, observed_at, retrieved_at (nullable until actually fetched), published_at (nullable), checked_at (nullable), metadata_json, metadata_fingerprint_sha256, content_hash_sha256 (nullable), source_status, schema_version | Immutable versioned record of what CIN received or observed |
| claim | claim_id, canonical identity fields, created_at, schema_version, identifier_method | Stable, content-derived claim identity |
| claim_assessment_event | assessment_event_id, claim_id, claim_status, assessed_at, methodology_version, assessor_type, rationale | Append-only history of claim status; never overwrite prior decisions |
| claim_evidence_relationship | relationship_id, claim_id, cin_evidence_id, relationship_type, review_status, rationale, created_at, schema_version | Explicit many-to-many traceability |
| evidence_conflict | conflict_id, subject_key, metric_or_predicate, observation_ids, detected_at, methodology_version, resolution_status | Preserve disagreement instead of silently selecting a preferred source |

All timestamps must be timezone-aware UTC instants. Keep source publication time, CIN observation time, CIN retrieval time, and human review time as distinct fields. Never synthesize a retrieval timestamp for caller-submitted metadata.

## 3. Identity, idempotency, and integrity

- Generate cin_evidence_id at the CIN ingestion boundary; retain caller IDs as (source_namespace, external_evidence_id) and do not assume global uniqueness.
- Use a unique constraint on (source_namespace, external_evidence_id) only when both values are present. If a provider reuses an external ID for materially changed content, retain the new observation under the same evidence record.
- Deduplicate observations using a canonical metadata fingerprint plus source identity and observation time. Fingerprints indicate equality of normalized supplied metadata only; they are not signatures or authenticity proof.
- A content hash may be stored only for bytes CIN is authorized to retrieve and retain. A hash proves byte equality, not source authenticity or truth.
- Claim IDs are derived from canonical claim identity as implemented in schema v1.0. Any future canonicalization change requires a new identifier-method version, not silent reinterpretation.
- Relationship rows require foreign keys to existing claims and CIN evidence records. Deleting or merging records must preserve an auditable tombstone/reference trail where legally permitted.

## 4. Lifecycle

1. **Receive:** validate schema, size, timestamps, URL policy, and caller identity; mark all caller assertions as unverified input.
2. **Normalize:** create CIN evidence identity and an immutable observation; record observed_at at actual receipt. retrieved_at remains null for caller-submitted metadata.
3. **Extract claim:** create a claim only from an explicit non-empty statement. Initial status is not_assessed.
4. **Link:** create a context_only relationship for traceability. It must not imply support or contradiction.
5. **Assess:** only a separately versioned evidence rule or authorized human review may create a new assessment event. Preserve rationale, evidence set, method version, and assessor type.
6. **Conflict:** preserve all conflicting observations and create an explicit conflict record. No recency-only or source-role-only winner selection.
7. **Refresh:** append a new observation; do not mutate the historical observation.
8. **Expire/delete:** apply a documented retention policy; remove or redact permitted data, retain only legally allowed minimal audit metadata, and record deletion completion without retaining deleted payloads.

## 5. Storage and transaction requirements

- Select a storage engine only after deployment topology, backup/restore, concurrency, and retention requirements are confirmed. A local ephemeral filesystem or SQLite file on an ephemeral service is not an acceptable durable production store.
- For a low-cost prototype, a local SQLite adapter may be used only for deterministic local tests and development. Production persistence requires a durable managed volume or database with backups and tested restore.
- Use migrations with explicit schema versions and reversible/forward-recovery procedures. Never run schema mutation automatically at application import/startup.
- Commit evidence record, observation, claim, and relationship atomically where they are created in one request. Enforce foreign keys and unique constraints at the database layer.
- Keep credentials outside source control; encrypt transport and backups; apply least-privilege access. No secret material is stored in evidence records.
- Do not introduce a background collector or external write integration as part of this persistence design.

## 6. API compatibility and exposure

- Existing assessment endpoints remain backward-compatible and read-only.
- Future persistence endpoints must be separately versioned and reviewed; ingestion must not fetch arbitrary URLs.
- Response payloads must distinguish caller_supplied_metadata, cin_observed_metadata, and cin_retrieved_source.
- Expose stable CIN IDs separately from external IDs. Never imply an external ID was authenticated.
- Return claim assessment status, relationship review state, observation timestamps, conflict state, and provenance caveats.
- Add pagination and bounded response sizes before exposing persisted history.
- Do not expose private operational notes, credentials, or restricted source content.

## 7. Acceptance gates before implementation

- [ ] Confirm source licensing, terms, and authorization for every provider and data type.
- [ ] Define data classification, privacy basis, retention duration, deletion workflow, and backup deletion policy.
- [ ] Select durable storage based on actual deployment topology; document cost and free-tier limits.
- [ ] Approve schema migrations and uniqueness/idempotency behavior.
- [ ] Add migration tests, transaction rollback tests, duplicate-ingestion tests, and concurrent-write tests.
- [ ] Add deletion/retention tests and verify backups do not silently defeat deletion commitments.
- [ ] Add API authorization and rate limits before any write endpoint is exposed.
- [ ] Validate source-fetch SSRF protections separately before any retrieval connector exists.
- [ ] Keep relationship promotion gated by explicit methodology and human review.
- [ ] Run offline CI; separately plan authorized live acceptance and deployment approval.

## 8. Explicit non-goals

This design does not authenticate issuers, auditors, custodians, reserve reports, or source URLs; prove claims; certify commodity backing; infer investment quality; crawl arbitrary links; store full documents by default; execute trades; control wallets; or move funds.

**Current implementation status:** shared claim builders and additive in-memory assessment response objects exist. Persistence and this lifecycle are design-only. Step 23 remains Partial.
