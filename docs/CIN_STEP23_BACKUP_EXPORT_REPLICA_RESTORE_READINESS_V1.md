# CIN Step 23 — Backup, Export, Replica, and Restore Readiness v1

**Status:** Architecture/readiness review only; no backup or erasure control is implemented or activated by this document.  
**Scope:** Future persistent CIN evidence data, derived data, exports, caches, backups, replicas, and restore workflows.  
**Current boundary:** Public evidence API remains read-only; SQLite is a local reference adapter; no production persistence or deployment is authorized.

## 1. Executive finding

The current Step 23 repository work defines lifecycle requirements for backups, replicas, exports, caches, and restore replay, but the reviewed implementation artifacts do not establish an operational backup system, export inventory, replica inventory, backup-expiry scheduler, restore-time erasure replay, or end-to-end residual-data verification.

This is an implementation-evidence gap, not proof that an external hosting provider has no backups. Provider-managed copies and retention behavior must be separately inventoried and verified before any production persistence decision.

**Disposition:** Backup/export/replica/restore lifecycle is design-documented but operationally unverified and not production-ready.

## 2. Asset and control matrix

| Asset | Minimum inventory fields | Required lifecycle behavior | Evidence currently available |
|---|---|---|---|
| Primary database | Environment, store ID, data classes, policy versions, owner | Policy-controlled access, retention, erasure and audit | Local SQLite reference schema/tests only |
| Automated database backups | Backup ID, creation time, source snapshot, encryption/access owner, expiry | Bounded expiry; deletion obligations propagated or replayed | No CIN backup job/configuration evidence reviewed |
| Provider/host-managed backups | Provider, service, region, terms, retention window, restore process | Document residual retention and deletion limitations | Not verified; provider documentation/account review required |
| Replicas/read replicas | Replica ID, source, lag, region, sync mode | Propagate approved erasure and policy changes; verify convergence | No CIN replica implementation evidence reviewed |
| Exports/downloads | Export ID, requester/authorization, included record IDs, destination, creation/expiry | Inherit strictest source classification/expiry; no retention extension | No governed export workflow evidenced |
| Support bundles | Bundle ID, scope, redaction result, recipient, expiry | Payload-free by default; explicit review for any included data | No governed support-bundle workflow evidenced |
| Caches/materialized views | Key/record lineage, creation/expiry, backing source | Source-linked expiry; invalidate after erasure | No Step 23 lifecycle enforcement evidenced |
| Restore artifacts | Backup ID, restore job, target, policy version | Replay erasure/tombstones before data becomes queryable | No restore replay implementation evidenced |
| External copies | Destination/controller, transfer record, data scope | Report outside-control copies as unresolved; never claim global erasure | No external export control evidenced |

## 3. Required lineage and manifest contract

Any future governed copy/export must have a payload-free control manifest with:
- immutable artifact ID and artifact type;
- source environment/store and exact source snapshot or record/observation IDs;
- data classification and retention policy version inherited from source;
- creation timestamp and the clock semantics used;
- destination/controller and access owner;
- encryption and access-control reference (not secret material);
- expiry/rotation policy reference;
- erasure dependency watermark or tombstone sequence;
- completion state and verification timestamp.

The manifest must not contain raw evidence payloads, credentials, private keys, seed phrases, or unrestricted raw hashes. Missing source lineage or policy reference blocks governed export/replication. A copy cannot receive a later expiry merely because it was copied.

## 4. Restore safety contract

Before a restored dataset is made queryable:
1. Identify the exact backup and source policy versions.
2. Verify backup integrity and access authorization without treating a checksum as proof of source authenticity.
3. Load approved erasure/tombstone events and policy changes newer than the backup snapshot.
4. Replay those events idempotently against the restored dataset and all derived indexes/caches.
5. Reconcile held, partially erased, failed, and unresolved records without guessing.
6. Run residual scans for erased payload IDs, active relationships, derived fingerprints/hashes, exports and caches.
7. Verify foreign keys, append-only invariants, policy references, and record counts.
8. Produce a controlled restore report with counts and exception IDs, excluding payloads.
9. Keep the restored system isolated and non-queryable if replay or verification fails.
10. Require an explicit release decision before reopening reads.

A backup that cannot support required erasure replay must not be represented as a compliant recovery source. Restore must never silently resurrect previously erased data.

## 5. Export and support-bundle safety contract

- Export scope must be explicitly authorized and bounded.
- Classification is the strictest classification among included items.
- Retention cannot exceed the earliest source obligation unless a separate approved policy permits it.
- Default support diagnostics are metadata-only and payload-free.
- Redaction must be tested before export, not assumed from a UI label.
- Record recipient, destination, creation time, expiry, and deletion confirmation where destination control permits.
- External destinations outside CIN control remain an explicit unresolved erasure dependency.
- No fingerprints or hashes are included merely as convenient identifiers.

## 6. Backup/replica deletion and expiry contract

- Every backup/replica must have an immutable creation time and approved maximum age/rotation rule.
- Source erasure must create a dependency event for all known copies.
- For immutable backups, define whether deletion is achieved by expiry, cryptographic erasure, or restore-time replay; do not claim immediate physical deletion without evidence.
- Replica deletion must be confirmed at each replica, not inferred from primary-store success.
- Backup expiry must account for legal holds and approved exceptions without silently extending unrelated records.
- Restore must replay all relevant erasure events before serving data.
- Partial or unobservable copy deletion remains unresolved, never erasure-verified.

## 7. Minimum test suite before activation

- Backup manifest includes exact source snapshot and policy version.
- Missing lineage/policy blocks backup or export creation.
- Export inherits strictest classification and earliest expiry across mixed inputs.
- Copying data does not reset source retention clocks.
- Erasure event propagates to each replica and cache.
- Immutable backup expiry and restore replay remove erased records before query access.
- Restore replay is idempotent across repeated restore attempts.
- Replay failure quarantines restore and prevents query exposure.
- Residual scan detects payload, relationship, fingerprint, hash, cache and export remnants.
- External destination without deletion confirmation remains unresolved.
- Legal hold affects only its approved exact scope.
- Audit reports expose counts/statuses but no payloads or secrets.

## 8. Evidence gaps and decisions required

| Gap / decision | Required evidence | Current status |
|---|---|---|
| CIN-owned backup design | Approved architecture, owner, schedule, encryption/access design | Not evidenced |
| Hosting-provider backup terms | Provider documentation and account/service review | Not verified |
| Replica inventory | Architecture and deployment inventory | Not evidenced |
| Export/support-bundle authorization | Scope, role, redaction, recipient and expiry policy | Not implemented |
| Cache inventory and invalidation | Runtime inventory and lineage/TTL contract | Not evidenced |
| Restore replay | Implemented, tested tombstone/policy replay and quarantine | Not implemented |
| Backup/replica expiry periods | Source-specific approved retention policy | Not approved |
| Legal hold and exceptions | Authenticated authority and exact-scope workflow | Not approved |
| External-copy deletion | Destination controller and verifiable deletion evidence | Not established |
| Production release | Explicit project approval after acceptance tests | Not authorized |

## 9. Safe implementation order

1. Inventory actual storage and copy locations without enabling new persistence.
2. Identify provider-managed backup/replica behavior from current service terms and configuration.
3. Approve source-specific retention and copy-expiry policy.
4. Define a versioned manifest and lineage schema in a separately reviewed schema version.
5. Implement read-only inventory/reporting first.
6. Implement export restrictions and backup/replica expiry only after policy approval.
7. Implement restore quarantine and erasure replay with deterministic tests.
8. Validate residual scans and failure handling.
9. Obtain explicit project approval before production persistence or operational activation.

## 10. Explicit non-actions

No backup, replica, export, cache, or restore service was created, configured, or changed. No data was copied, deleted, backfilled, or migrated. No hosting-provider retention behavior is asserted. No retention period, legal basis, hold authority, or erasure guarantee is invented. No deployment or production persistence was activated.

**Disposition:** Readiness requirements and evidence gaps are now explicit. Operational controls remain unverified; Step 23 remains Partial.
