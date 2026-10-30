# CIN Step 23 — Persistence and Evidence Lifecycle Design

**Status:** Design plus partial local SQLite reference implementation. This document itself is not an implementation; the migration and adapter are local-only, are not wired to the public API, and are not production persistence. No retention job or public persistence endpoint is implemented.  
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


## 9. Reference schema increment (2026-10-30)

A SQLite DDL reference migration is now present at database/migrations/0001_claim_evidence_schema_v1.sql, with in-memory schema tests in tests/test_cin_evidence_schema_v1.py. The tests exercise entity/index creation, namespaced external-ID uniqueness, foreign-key enforcement, constrained assessment vocabulary, and JSON validation.

This file is a **reference schema for local development/tests only**. It is not applied by application startup, is not connected to an API or repository adapter, and is not a production persistence implementation. The SQL uses SQLite JSON functions and must not be assumed portable to another database engine. Before adoption, validate timestamp normalization, migration runner behavior, transactional semantics, backup/restore, retention/deletion, and the selected durable production database.


## 10. Local repository adapter increment (2026-10-30)

Added cin_local_sqlite_evidence_repository.py as an explicit-connection, local-development-only adapter. It does not initialize a database, run migrations, attach to the API, fetch URLs, or configure production storage. The caller must explicitly create a connection and apply the reference schema.

The adapter writes one evidence record, immutable observation, claim, initial assessment event, and claim/evidence relationship inside one SQLite transaction. It assigns a CIN-owned evidence ID and stores the caller's external ID separately. Caller-submitted metadata retains source_status=caller_supplied and retrieved_at=NULL. The adapter does not infer claim truth or promote relationship review state.

Offline tests cover successful atomic writes, duplicate external identity rollback, timezone-aware timestamp validation, and rejection of non-finite metadata. This is not durable production persistence and does not change assessment API behavior or Render deployment.


## 11. Append-only assessment history (2026-10-30)

The local SQLite adapter now exposes append_assessment_event(...). It inserts a new claim assessment event with an explicit assessment timestamp, methodology version, assessor type, status, and rationale. It never updates or deletes an earlier event. The operation validates the status and assessor vocabularies, requires a timezone-aware timestamp and bounded rationale, and relies on the claim foreign key. Tests verify a second assessment leaves the initial event intact and rejects an unknown claim or unsupported status.

This remains local development/test functionality. It is not connected to a user-facing assessment workflow, does not establish that a human reviewer identity is authenticated, and does not authorize status promotion without a governed review process.


## 11. Append-only lifecycle operations (2026-10-30)

The local-only adapter now supports appending a new observation to an existing CIN evidence record and appending claim assessment events without updating prior rows. New observation writes validate timezone-aware timestamps, JSON-serialize finite metadata, compute a normalized metadata fingerprint, and rely on the database foreign key to reject unknown evidence IDs. Regression tests verify historical observations remain unchanged, UTC normalization is applied, and invalid writes do not add rows. These operations remain local SQLite development/test functionality only; there is no API wiring, retention worker, or production durability.


## 12. Database-enforced append-only history and current limitations (2026-10-30)

The local SQLite reference migration now installs four database triggers:

- `trg_cin_evidence_observations_no_update` and `trg_cin_evidence_observations_no_delete`
- `trg_cin_claim_assessment_events_no_update` and `trg_cin_claim_assessment_events_no_delete`

These guards apply even when SQL is issued outside the repository adapter. Regression tests attempt direct SQL updates and deletes and verify that SQLite rejects the mutations without changing the stored history. Migration tests also reapply schema v1.0 and assert that exactly one instance of each guard remains.

**Important retention/deletion interaction:** the v1.0 reference triggers intentionally block deletion of observations and assessment events. This is an integrity safeguard for local tests, not an approved permanent-retention policy. It currently means a retention or erasure workflow cannot delete those rows through this schema. Before any real persistence is enabled, CIN must define the applicable retention, privacy, legal-erasure, backup-expiry, and audit requirements, then design and test an explicitly versioned retention mechanism. Do not silently disable these triggers or treat append-only storage as overriding a valid deletion obligation.

**Current implementation boundary:** the triggers and tests apply only to the local SQLite reference migration. They do not establish production durability, authenticated reviewer identity, source authenticity, API write authorization, or a production retention policy. The API remains read-only and persistence remains opt-in/local-only.


## 13. Retention and erasure design gate (2026-10-30)

**Decision: no deletion migration or retention worker is authorized by the current project requirements.** The v1.0 append-only triggers remain unchanged. A retention duration, legal basis, data classification, source licence, and backup-expiry requirement must be approved before implementation; inventing a universal retention period would create an unsupported compliance and data-loss policy.

### 13.1 Separate the data lifecycle classes

| Data class | Proposed treatment | Required decision before implementation |
|---|---|---|
| Raw/normalized provider metadata payload | Eligible for policy-driven purge or redaction | Provider terms, permitted retention, and maximum age |
| Derived metadata fingerprint/content hash | Retain only if it cannot reasonably reconstruct or identify erased content and policy permits it | Privacy review and hash-retention rationale |
| Evidence record identity and provenance pointer | Retain a minimal tombstone only where lawful and necessary | Audit purpose, legal basis, and minimum fields |
| Observation history | Append-only during its approved retention window; expiry handled by a versioned controlled process | Per-source retention class and deletion scope |
| Claim assessment events | Preserve decision history only as long as justified; erase or pseudonymize reviewer data when required | Reviewer privacy and audit requirements |
| Claim/evidence relationships and conflicts | Remove or detach references when the underlying evidence is erased, without leaving misleading active relationships | Referential-integrity and conflict-history policy |
| Backups and replicas | Expire erased data through documented backup rotation; disclose the maximum residual period | Backup schedule, restore procedure, and expiry SLA |

### 13.2 Required deletion workflow

A future retention implementation must be a separately versioned migration and controlled application operation, not a general-purpose DELETE method on the evidence repository.

1. Identify records by approved retention class and policy version; support legal holds and explicit exemptions.
2. Produce a dry-run manifest containing record IDs, data classes, age basis, and intended action. Do not include payload contents.
3. Require an authorized operator or approved policy engine to approve the manifest; record the policy version and authorization context.
4. In one database transaction, mark the record as pending erasure, remove or redact eligible payload fields, and deactivate dependent relationships/conflict references as specified by policy.
5. Retain only the minimum permitted tombstone/deletion event: opaque record reference, policy version, completion timestamp, action category, and non-sensitive outcome. Never copy erased payload into the audit event.
6. Verify postconditions by querying for residual payload and active references; report exceptions rather than claiming deletion succeeded.
7. Expire affected backups/replicas according to the approved backup policy, and verify through restore testing that erased payload is not reintroduced.
8. Keep legal holds, failed deletions, and partial completion visible as unresolved states; never silently bypass append-only triggers.

### 13.3 Migration and testing requirements

- Do not drop or disable the v1.0 append-only triggers in place. Introduce a new schema version with explicit migration and forward-recovery instructions.
- Prefer a dedicated retention operation with narrow permissions over allowing application roles to issue arbitrary deletes.
- Test legal-hold exclusion, dry-run determinism, idempotent retries, partial failure, transaction rollback, foreign-key cleanup, tombstone minimization, backup expiry, and restore behavior.
- Test that ordinary ingestion and assessment code cannot invoke retention operations.
- Keep the current API read-only and the SQLite adapter local-only until all policy and deployment gates are approved.

### 13.4 Unresolved policy decisions

The following are intentionally not guessed or implemented:

- Retention periods by provider, evidence type, and data classification.
- Applicable privacy/legal basis and erasure exceptions.
- Whether any source metadata or derived hashes may be retained after payload erasure.
- Who may authorize deletion and how that authority is authenticated.
- Legal-hold scope and release procedure.
- Backup/replica expiry limits and restore-time deletion replay.
- Whether minimal tombstones are permitted or required for each source class.

**Acceptance status:** design documented; implementation blocked pending these policy decisions. No trigger has been disabled, no record has been deleted, and no retention schedule or worker has been enabled.


## 14. Derived hash and fingerprint lifecycle design gate (2026-10-31)

See `docs/CIN_STEP23_DERIVED_DATA_HASH_AND_FINGERPRINT_LIFECYCLE_V1.md` for the detailed F-07 proposal. Current behavior is limited: the local adapter stores SHA-256 fingerprints of canonicalized allowlisted metadata; the optional content-hash column is currently populated with NULL. Neither is proof of authenticity or anonymity. Default future treatment is to inherit source classification, policy version, lineage, and expiry; source erasure triggers a dependency review and removal of derived descendants unless a narrow, independently approved retention exception is fully justified. Missing lineage fails closed. No current hash is changed or deleted; no new hash computation, lineage schema, retention worker, or production persistence is enabled. This is a design gate only.


## 15. Classification implementation-readiness gate (2026-10-31)

See `docs/CIN_STEP23_F03_CLASSIFICATION_IMPLEMENTATION_READINESS_V1.md` for the field-level candidate mapping, proposed schema-v2 policy registry contract, fail-closed semantics, migration/backfill sequence, acceptance tests, and unresolved approval register. This plan is non-executable design guidance: no classification or retention labels are present in schema v1.0, no rows are backfilled, and no policy duration, legal basis, source permission, or legal-hold authority is approved by this document. Schema-v2 implementation remains blocked until each required decision has explicit evidence and the migration receives separate review and project approval.


## 16. Backup, export, replica, and restore readiness gate (2026-10-31)

See `docs/CIN_STEP23_BACKUP_EXPORT_REPLICA_RESTORE_READINESS_V1.md` for the asset/control matrix, copy-manifest contract, restore quarantine and erasure-replay sequence, export/support-bundle boundaries, acceptance tests, and evidence gaps. This review found no repository evidence of an operational CIN backup job, replica inventory, governed export workflow, or restore-time erasure replay. Provider-managed copies were not independently verified; this is an evidence gap, not a claim that hosting providers keep no backups. No copy, export, backup, restore, data, or deployment was changed. Operational lifecycle remains unverified and production persistence remains unauthorized.


## 17. Access-control and authorization readiness gate (2026-10-31)

See `docs/CIN_STEP23_ACCESS_CONTROL_AND_AUTHORIZATION_READINESS_V1.md` for the current trust-boundary inventory, proposed principal/permission model, fail-closed requirements, privileged-operation controls, acceptance tests, and unresolved decisions. Reviewed API validation and dependency injection are not authentication or authorization; the SQLite adapter has no role enforcement and connection possession is not production identity. No authentication, permissions, schema, secrets, API write path, or deployment configuration was changed. Privileged operations remain unauthorized.


## 18. Public endpoint abuse and rate-limit readiness gate (2026-10-31)

See `docs/CIN_STEP23_PUBLIC_ENDPOINT_ABUSE_AND_RATE_LIMIT_READINESS_V1.md` for the public evidence-ingestion request/provider resource review, threat scenarios, caller/global quotas, concurrency/backpressure, provider-429 handling, telemetry, acceptance tests, and unresolved deployment evidence. The connector already has a fixed provider destination, bounded timeout, and 1,000,000-byte response limit; per-caller/global throttling and concurrency controls were not evidenced in the reviewed route/connector. No middleware, edge rule, runtime code, provider quota, or deployment setting was changed. Abuse-control readiness remains open.


## 19. Operational logging, monitoring, and incident-response readiness gate (2026-10-31)

See docs/CIN_STEP23_OPERATIONAL_LOGGING_MONITORING_INCIDENT_RESPONSE_READINESS_V1.md for the reviewed sanitized API error behavior, offline CI evidence, candidate minimized event schema, monitoring indicators, incident runbook requirements, acceptance gates, and unresolved operational ownership/retention questions. The bundled application entry point and hosting-level logging behavior were not independently inspected in this pass and remain not assessed. No runtime telemetry, alert, incident automation, log retention policy, or deployment setting was changed. Operational readiness remains open.


## 20. Disaster recovery and service continuity readiness gate (2026-10-31)

See docs/CIN_STEP23_DISASTER_RECOVERY_AND_SERVICE_CONTINUITY_READINESS_V1.md for service-tier RTO/RPO decision requirements, provider/platform/release/overload failure scenarios, safe degradation, staged recovery sequence, and continuity test gates. This is distinct from the backup/export/replica/restore lifecycle: it addresses service availability and controlled restoration of service. No RTO/RPO targets, standby, failover, monitor, release gate, retry loop, hosting configuration, or deployment was changed. Operational recovery remains unimplemented and unverified.


## 21. Provider governance and source-of-truth integrity readiness (2026-10-31)

See docs/CIN_STEP23_PROVIDER_GOVERNANCE_AND_SOURCE_OF_TRUTH_READINESS_V1.md for the provider registry contract, metric-specific source precedence, fallback eligibility, provenance preservation, conflict handling, and acceptance tests. This is a governance/readiness design, not a runtime registry or provider certification. The current GitHub evidence connector remains narrowly allowlisted, bounded, and explicitly unverified; its 7-day activity freshness threshold is not a universal metric freshness policy. No provider, fallback, cache, retry, source priority, or live retrieval was changed. Cross-provider governance remains open.


## 22. Claim conflict and review-state readiness (2026-10-31)

See docs/CIN_STEP23_CLAIM_CONFLICT_AND_REVIEW_STATE_READINESS_V1.md for the distinction between relationship vocabulary validation and actual conflict detection/adjudication. The shared primitives validate relationship/review-status values but do not authenticate reviewers, compare evidence, execute state transitions, or persist review events. No claim was adjudicated or status promoted. Conflict detection, authenticated review, and durable resolution history remain unimplemented.


## 23. Evidence completeness and coverage readiness (2026-10-31)

See docs/CIN_STEP23_EVIDENCE_COMPLETENESS_AND_COVERAGE_READINESS_V1.md for the expected-source manifest, source/entity/metric/time/field/pagination/provenance coverage dimensions, scan-gap accounting, assessment status rules, and acceptance tests. The common evidence model specifies completeness fields, while the reviewed GitHub connector has only source-specific missing-field/freshness reporting and the cross-source comparator accepts caller-supplied observations without an expected coverage denominator. No general coverage evaluator, scheduler, pagination client, provider query, API, schema, or persistence activation was added. Runtime completeness enforcement remains open.


## 24. Assessment methodology and reproducibility readiness (2026-10-31)

See docs/CIN_STEP23_ASSESSMENT_METHODOLOGY_AND_REPRODUCIBILITY_READINESS_V1.md for the reproducibility envelope, methodology versioning, deterministic calculation requirements, module-specific risks, minimum persisted snapshot contract, and acceptance tests. Existing coin-screening weights are documented, and several functions accept explicit clocks/parameters, but no common methodology registry, immutable input snapshot, pinned execution fingerprint, component-level lineage, or end-to-end replay facility is evidenced. No formulas, defaults, source data, schema, runtime, or persistence activation changed. Exact historical reproducibility remains unimplemented.


## 25. Assessment quality assurance and validation readiness (2026-10-31)

See docs/CIN_STEP23_ASSESSMENT_QUALITY_ASSURANCE_AND_VALIDATION_READINESS_V1.md for the test taxonomy, requirement-to-evidence traceability, ground-truth governance, independent review, false-positive/false-negative measurement, temporal/universe controls, module-specific edge cases, reproducibility requirements, and proposed release/rollback gates. Existing offline unit and regression tests cover meaningful input validation and module behavior across coin screening, commodity backing, growth fundamentals, and cross-source comparison. They do not establish a unified benchmark/ground-truth registry, independent validation protocol, shared error-rate reporting, calibrated probabilistic output, or production drift monitoring. No numeric performance thresholds were invented. No runtime code, test suite, scoring formula, provider, schema, API, persistence behavior, or deployment was changed. F-17 readiness design is documented; unified QA and independent validation remain unimplemented. Step 23 remains Partial.
