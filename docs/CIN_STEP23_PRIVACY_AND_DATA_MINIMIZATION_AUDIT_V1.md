# CIN Step 23 — Privacy and Data-Minimization Audit v1

**Audit date:** 2026-10-30  
**Scope:** source review of the Step 23 evidence ingestion, mapping, claim model, persistence orchestration, local SQLite adapter, and SQLite reference schema on the Step 23 branch.  
**Status:** findings and recommendations only; no production privacy certification, legal assessment, or runtime enforcement is implied.  
**Boundary:** API remains read-only; persistence remains opt-in/local-only. No deployment, production storage activation, trade execution, wallet access, or fund movement.

## 1. Executive result

The reviewed code has useful safeguards: GitHub retrieval is restricted to a fixed allowlist and fixed API root; provider responses are byte-bounded; selected fields and timestamps are validated; GitHub snapshots remain explicitly unverified; the evidence mapper is pure; and the SQLite adapter requires an explicitly supplied connection.

However, these safeguards do not constitute a general sensitive-data policy. The persistence adapter accepts caller-provided metadata and text fields without a data-classification model, field allowlist, recursive sensitivity screening, or independent stored-payload size ceiling. The reference schema does not carry a retention class or classification label. These are pre-production design gaps.

No evidence from this source review establishes that sensitive data has been disclosed or misused.

## 2. Findings

### F-01 — Arbitrary metadata object is persisted without a field allowlist

**Evidence:** `LocalSQLiteEvidenceRepository.store_bundle(...)` and `append_observation(...)` accept a dictionary and JSON-serialize it. The schema stores the serialized object in `metadata_json` with JSON validity checks, but no field allowlist, recursive shape/depth bound, or sensitive-field rejection is applied.

**Risk:** callers could persist unrelated personal data, credentials, access tokens, private notes, or unexpectedly large nested structures. The current GitHub connector returns a constrained object, but the repository adapter is a broader interface and should not rely on one caller's discipline.

**Recommendation:** define source-specific metadata schemas and allowlists; reject unknown fields by default; enforce maximum serialized bytes, nesting depth, collection length, string length, and numeric bounds at the persistence boundary. Do not attempt to make generic secret scanning the only control.

### F-02 — Claim statements and rationales are not sensitivity-screened

**Evidence:** claim `subject`, `statement`, relationship `rationale`, and assessment `rationale` are bounded text fields. Validation enforces non-empty text and maximum lengths, but does not define permitted content classes.

**Risk:** user-submitted or operator-entered text could accidentally contain personal identifiers, contact details, credentials, or confidential material.

**Recommendation:** define permitted content and prohibited content for each text field. Prefer references to approved evidence IDs over copying source text. Add explicit validation for known secret formats where appropriate, while documenting that pattern scanning cannot guarantee detection. Never store passwords, API tokens, private keys, seed phrases, authentication headers, or wallet secrets.

### F-03 — No explicit data classification or retention class in schema v1.0

**Evidence:** evidence records and observations have source namespace, type, timestamps, metadata and status fields, but no classification or retention-policy version/class.

**Risk:** a future retention process cannot reliably determine treatment from schema data alone without external undocumented rules.

**Recommendation:** add classification and retention-class fields only in a separately reviewed schema version, with controlled vocabularies and source-specific defaults. Link each stored record to the applicable policy version. Do not silently alter schema v1.0.

### F-04 — Stored-payload size is not independently bounded by the repository

**Evidence:** the GitHub connector reads at most 1,000,000 response bytes, but repository methods accept arbitrary dictionaries and serialize them without a maximum encoded payload size.

**Risk:** callers other than the GitHub connector could cause excessive storage, memory use, or unexpectedly large database rows.

**Recommendation:** enforce a repository-level maximum on canonical UTF-8 JSON bytes before opening the write transaction. Use a lower source-specific limit where practical. Test boundary, over-limit, deeply nested and non-finite values.

### F-05 — Provenance timestamps are validated, but retention semantics remain incomplete

**Evidence:** the adapter validates timezone-aware timestamps and distinguishes observed/retrieved/published/checked fields. It does not attach a retention class or expiry decision.

**Risk:** timestamps alone do not define which clock starts a retention period or how stale, corrected, disputed, or legally held evidence should be handled.

**Recommendation:** define the retention start event per source class (for example, retrieval or closure of an assessment), and make expiry decisions reference a policy version. Keep legal holds and deletion approvals explicit. This finding must be resolved together with the retention/erasure design document.

### F-06 — API provider errors are controlled, but disclosure review remains required

**Evidence:** known provider failures become HTTP 502 responses; unexpected exceptions return a generic message. The explicit `EvidenceSourceError` message is passed to the client and currently contains status codes, bounded field names, or exception class names rather than response bodies.

**Risk:** future provider exceptions could include URLs, query parameters, identifiers, or response fragments if message construction changes.

**Recommendation:** keep client-facing errors generic and stable; put only sanitized diagnostic categories in logs; never log request headers, tokens, full provider payloads, or raw exception objects. Add tests that assert response bodies do not contain injected secret markers or raw provider response bodies.

### F-07 — Hashes and fingerprints need a clear data lifecycle

**Evidence:** metadata fingerprints are stored; optional content hashes are represented in the schema. The lifecycle documentation already notes that hashes are not authenticity proof.

**Risk:** hashes can remain linkable and may permit confirmation of known content. They should not automatically be treated as anonymous or harmless after payload erasure.

**Recommendation:** classify hashes as derived data, document their purpose, and include them in retention/erasure decisions. Retain a hash after payload deletion only where a documented purpose and approved policy permit it.

### F-02 implementation note — local persistence boundary

The local SQLite reference adapter now applies field-specific maximum lengths and conservative pattern screening before opening write transactions for claim subject/predicate/statement/unit/identifier method, relationship rationale, assessment methodology version, and assessment rationale. It rejects recognizable PEM private-key headers, Bearer credential strings, selected common provider-token prefixes, and explicit secret/recovery-phrase labels. Nested claim values also reject sensitive key names such as `api_key`, `private_key`, `seed_phrase`, `mnemonic`, `authorization`, and `token`.

Regression tests cover rejection before writes, field-length enforcement, assessment history preservation, and acceptance of ordinary research rationale text. The checks are defense-in-depth only: they are not a general DLP engine, do not identify every credential format, and do not reliably detect an unlabeled mnemonic or arbitrary personal data. No claim text is sent to an external scanning service. These checks apply only to the explicit local SQLite adapter; they do not establish API write authorization or production enforcement.

## 3. Controls already present (do not overstate)

- Public GitHub retrieval uses a fixed API root and three-repository allowlist; arbitrary URL fetching is not supported by this connector.
- Provider response bytes are capped at 1,000,000 before JSON parsing.
- Repository identity, selected metadata field types, timestamps, and freshness are validated.
- The mapper rejects failed, non-allowlisted, or verification-promoted snapshots and keeps the claim `not_assessed` and relationship `context_only`.
- The API does not write through its injected store; persistence remains unwired.
- The local SQLite adapter requires a caller-supplied connection and does not initialize a database or migration.
- Append-only triggers protect observation and assessment event rows in the local reference schema.

These controls reduce specific risks; they do not amount to a comprehensive privacy/security program or production authorization.

## 4. Required pre-production controls

Before any production persistence is proposed, require:

1. A source-specific schema/allowlist for every persisted metadata type.
2. A data classification and prohibited-data policy covering evidence, claims, rationales, logs, hashes, exports and backups.
3. Repository-level byte, depth, field-count, string-length and collection-size limits.
4. Explicit rejection of credentials, API tokens, private keys, seed phrases and wallet secrets; no wallet-related data collection is in CIN scope.
5. A retention class and policy version for every record, aligned with the retention/erasure design gate.
6. Sanitized API errors and structured logs with no raw payloads or secrets.
7. Tests proving unknown fields, oversized/deep payloads and known secret markers are rejected or safely handled.
8. A review of backup, replica, export and restore paths so data-minimization and erasure controls apply beyond the primary database.

## 5. Audit disposition

| Finding | Disposition |
|---|---|
| F-01 Arbitrary metadata shape | Partially mitigated in local SQLite adapter: GitHub namespace allowlists plus recursive JSON depth/node/string/collection bounds. Other namespaces have structural bounds but no source-specific semantic allowlist; production enforcement remains open. |
| F-02 Free-text sensitivity | Partially mitigated in local SQLite adapter — conservative marker/length checks; full content classification and production controls remain open |
| F-03 Missing classification/retention class | Design proposal and implementation-readiness specification documented in `CIN_STEP23_DATA_CLASSIFICATION_AND_RETENTION_CLASSES_V1.md` and `CIN_STEP23_F03_CLASSIFICATION_IMPLEMENTATION_READINESS_V1.md`; field-level candidate assignments, schema-v2 contract, fail-closed semantics, migration sequence, tests, and unresolved approvals are explicit. No policy is approved and no schema/runtime enforcement exists |
| F-04 Missing repository payload byte ceiling | Implemented and tested in local SQLite adapter: canonical metadata is capped at 64 KiB before writes, including appended observations. This is not a provider-ingestion response limit or production storage guarantee. |
| F-05 Retention semantics | Clock/expiry design documented in `CIN_STEP23_RETENTION_CLOCKS_AND_EXPIRY_RULES_V1.md`; provider-specific terms, durations, approval and implementation remain open |
| F-06 Error disclosure regression protection | API boundary now returns one stable generic 502 detail for both known and unexpected provider failures; regression tests inject raw body, credential, token, and sensitive URL markers and assert they are not exposed. No raw exception logging was added. |
| F-08 Backup/export/replica/restore lifecycle | Design/readiness requirements documented; operational inventory, provider-managed copy review, expiry enforcement, and restore-time erasure replay are not evidenced |\n| F-07 Hash lifecycle | Derived-data lifecycle documented in `CIN_STEP23_DERIVED_DATA_HASH_AND_FINGERPRINT_LIFECYCLE_V1.md`; lineage, policy approval and implementation remain open |

**F-08 — Backup/export/replica/restore lifecycle is not operationally evidenced**\n\n**Evidence:** design documents specify backup expiry, replica propagation, export lineage, and restore-time erasure replay, but the reviewed repository does not establish an operational CIN backup job, replica inventory, governed export workflow, or restore replay implementation. Hosting-provider managed copies were not independently verified.\n\n**Risk:** deletion or expiry in a primary store could leave residual data in copies, exports, caches, or restored datasets; an unverified restore path could reintroduce erased records.\n\n**Recommendation:** inventory all copy locations and provider terms; require lineage/policy manifests, approved expiry, restore quarantine, idempotent erasure replay, and residual scans before production persistence. See `CIN_STEP23_BACKUP_EXPORT_REPLICA_RESTORE_READINESS_V1.md`.\n\n**Overall:** source review completed; privacy/data-minimization readiness is not yet established. These findings do not authorize production storage. The API remains read-only, SQLite remains a local reference implementation, and no deployment or paid service change is included.

### F-03 design increment — classification and retention classes (2026-10-31)

Added `docs/CIN_STEP23_DATA_CLASSIFICATION_AND_RETENTION_CLASSES_V1.md`. It defines separate sensitivity classifications and lifecycle retention classes, maps evidence/claims/rationales/hashes/logs/exports/backups to proposed defaults, and specifies fail-closed handling for unknown classifications and policy versions. It also defines a future policy-version contract and implementation acceptance gates. This is a design proposal only: no durations, legal basis, source authorization, or legal-hold authority were invented; schema v1.0 and all existing data remain unchanged. F-03 is design-documented but remains open pending policy approval and a separately reviewed schema version. F-05 and F-07 remain open.

### F-05 design increment — retention clocks and expiry rules (2026-10-31)

Added `docs/CIN_STEP23_RETENTION_CLOCKS_AND_EXPIRY_RULES_V1.md`. It defines distinct start events for provider snapshots, source versions, evidence identities, observations, claims, relationships, assessment/conflict events, derived fingerprints/hashes, diagnostics, exports, caches, backups, and tombstones. It specifies fail-closed handling for missing/invalid clocks, prohibits silent timestamp substitution and clock resets on re-ingestion/reassessment, and makes expiry eligibility distinct from deletion authorization. No durations, provider terms, legal basis, or hold authority were invented. No schema, records, scheduler, worker, or production persistence changed. F-05 is design-documented but remains open pending provider-specific approval.

### F-07 design increment — derived hash and fingerprint lifecycle (2026-10-31)

Added `docs/CIN_STEP23_DERIVED_DATA_HASH_AND_FINGERPRINT_LIFECYCLE_V1.md`. It records the current adapter behavior accurately (SHA-256 over canonical metadata; optional content-hash column currently written as NULL), explains linkability and known-content confirmation risks, requires exact source lineage and algorithm versioning, defaults derived expiry to source expiry, and defines a narrow independently approved retention exception. No current hash was changed/deleted; no content hashing, lineage schema, API, worker, or production persistence was added. F-07 is design-documented only and remains open pending approval and implementation.


### F-06 API error-disclosure regression increment (2026-10-31)

- Changed `POST /public-evidence-ingestion` so both expected `EvidenceSourceError` failures and unexpected provider exceptions return the same stable client-facing HTTP 502 detail: `Public evidence provider is temporarily unavailable`.
- Provider exception text is no longer passed through to API clients. The API does not log raw exception objects or provider payloads.
- Added regression coverage injecting raw provider-body markers, GitHub-style token markers, Bearer credentials, URL query credentials, and sensitive provider URLs into provider exception text. The tests assert a stable response and no marker disclosure.
- This protects the API response boundary only; it does not establish comprehensive log redaction, hosting-platform log controls, or production security certification. The endpoint remains read-only and persistence remains unwired.


### F-01 / F-04 audit status reconciliation (2026-10-31)

- F-01: the local SQLite adapter has a GitHub-specific top-level and nested-value allowlist, plus recursive bounds for JSON depth, node count, string length, and collection size. This partially mitigates F-01 for the implemented GitHub namespace. It does not create allowlists for every possible source namespace and is not production enforcement.
- F-04: the local SQLite adapter canonicalizes metadata and rejects payloads above 64 KiB before evidence-bundle or observation writes. Regression tests cover oversized initial metadata and oversized appended observations. This is a repository-level local adapter ceiling, not a provider HTTP response-byte ceiling or production guarantee.
- The earlier disposition table incorrectly left both findings fully Open; it now reflects the implemented scope and remaining limitations. No runtime code or data was changed in this reconciliation.


### F-03 implementation-readiness reconciliation (2026-10-31)

- Added `docs/CIN_STEP23_F03_CLASSIFICATION_IMPLEMENTATION_READINESS_V1.md` with a field-level candidate assignment matrix, candidate schema-v2 policy registry contract, fail-closed runtime semantics, additive migration/backfill sequence, acceptance tests, and approval register.
- This narrows the implementation plan but does not close F-03: classification vocabulary, source permissions, legal/privacy basis, durations/start events, hold authority, backfill rules, erasure/backup workflow, and production activation remain unapproved or unimplemented.
- Schema v1.0, existing rows, API behavior, and persistence activation are unchanged. F-03 remains Open pending policy approval and separate implementation review.


### F-08 backup/export/replica/restore readiness increment (2026-10-31)

- Added `docs/CIN_STEP23_BACKUP_EXPORT_REPLICA_RESTORE_READINESS_V1.md` defining the copy inventory, lineage manifest, export/support-bundle controls, restore quarantine and erasure replay, backup/replica expiry semantics, acceptance tests, and evidence gaps.
- Repository review did not find evidence of an operational CIN backup job, replica inventory, governed export workflow, or restore replay implementation. Provider-managed copies were not independently verified; this is an evidence gap, not a claim that a provider has no backups.
- No backup/export/replica/restore configuration or data was changed. F-08 remains Open pending inventory, provider review, policy approval, implementation and tests. Production persistence remains unauthorized.
