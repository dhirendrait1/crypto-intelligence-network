# CIN Step 23 — Retention Clocks and Expiry Decision Rules v1

**Status:** Design-only proposal; no retention periods or deletion jobs are approved.
**Compatibility:** SQLite schema v1.0 and existing records remain unchanged.

## 1. Terms and timestamp semantics

A retention clock is the event and timestamp from which an approved maximum age is measured. Expiry eligibility is not authorization to delete. Erasure completion requires verification across the primary store, derived data, references, exports, caches, logs, backups, and replicas in scope.

Provider publication time, provider update time, CIN observation time, CIN retrieval time, assessment time, and policy effective time are distinct. They must never be silently substituted for one another.

## 2. Clock selection rules

1. Every retention policy names one explicit start event and timestamp field; 'record date' is insufficient.
2. The selected event must match the data purpose and provider terms and must be recorded with its source and policy version.
3. Never replace a missing or invalid provider timestamp with current time, retrieval time, or another timestamp unless the approved policy explicitly defines that fallback.
4. If the required clock is missing, malformed, timezone-naive, unacceptably future-dated, or not linked to the intended event, mark the decision clock_unresolved and do not calculate expiry.
5. Any fallback must be provider-specific, deterministic, bounded, and explicitly distinguished from the primary clock.
6. Evaluate provider and other mandatory deadlines separately; the strictest applicable deadline controls, subject to valid scoped holds and exceptions.
7. Policy effective dates apply prospectively unless an approved migration explicitly defines backfill. Never retroactively infer clocks.
8. Re-ingestion, refresh, re-observation, reassessment, or export does not reset an existing data unit's clock. A genuinely new version is a new data unit with its own clock.
9. A legal hold pauses only the exact authorized scope; it does not reset unrelated clocks.
10. Expiry only makes a record eligible for review. A separately approved erasure workflow is required.

## 3. Proposed clock matrix

| Data unit | Candidate start event | Candidate timestamp | Refresh/reset rule | Missing clock behavior |
|---|---|---|---|---|
| Provider metadata snapshot | CIN successfully retrieves that exact snapshot | retrieved_at | Each snapshot has its own clock; newer snapshots do not reset older ones | Unresolved; do not substitute published_at without policy |
| Provider content version | Provider publishes or updates that exact version | published_at or provider updated_at | New version gets a new clock | Retrieval fallback only if policy explicitly permits it |
| Evidence identity | First accepted ingestion of identity | Proposed first_seen_at | Repeated observation does not reset | Unresolved unless trusted first-seen event is recorded |
| Observation row | CIN appends that observation | observed_at or a separately defined recorded_at | Each event has its own clock | Unresolved if chosen event time is absent |
| Claim version | CIN accepts exact claim version | claim creation/recorded timestamp | New version gets a new clock; never edit historical version in place | Unresolved; do not use evidence retrieval time |
| Relationship | CIN creates exact claim-evidence relationship | relationship_created_at | New relationship event gets its own clock | Unresolved |
| Assessment event | Assessment event is recorded | assessed_at or distinct recorded_at | Later assessments do not reset earlier events | Unresolved |
| Conflict event | Conflict is detected/recorded | explicit conflict_detected_at or recorded_at | Resolution does not rewrite original event | Unresolved |
| Metadata fingerprint | Fingerprint computed for exact snapshot | Proposed fingerprinted_at linked to snapshot | New fingerprint is a new derived item | Inherit source policy only with exact lineage |
| Content hash | Hash computed for exact authorized content version | Proposed hashed_at linked to content ID | New version gets new hash | Unresolved |
| Operational diagnostic | Diagnostic emitted | logged_at | Each log event has its own clock | Unresolved; never retain raw payload to compensate |
| Export/support bundle | Export generated | exported_at | Export must not extend source retention | Inherit strictest included-data obligation; unresolved if lineage missing |
| Cache entry | Cache value written | cached_at / TTL metadata | Refresh creates new entry; bounded source-aware TTL | Do not cache if expiry cannot be determined |
| Backup/replica | Copy created | backup_created_at / replica ingestion time | Each copy has its own lifecycle; erasure must propagate | Do not claim erasure complete until verified |
| Minimal tombstone | Erasure verified for stated scope | erasure_completed_at | Own approved minimal retention rule | Do not create without approved purpose and fields |

Names marked proposed are conceptual future-schema fields, not existing columns. Current schema timestamps must not be reinterpreted to fit this matrix.

## 4. Expiry calculation contract

For an approved policy version: expiry_at = retention_basis_at + approved_duration.

Calculate only when the applicable immutable policy, named basis event, valid timestamp, approved duration/unit, provider obligations, hold/exception status, and lineage are all resolved. Record each obligation separately and select the controlling deadline deterministically.

Suggested states (not current runtime values): not_assessed; clock_unresolved; policy_unresolved; not_yet_eligible; eligible_for_review; held; erasure_pending; erasure_partial; erasure_verified; exception.

## 5. Provider-specific policy record

Each source namespace and endpoint/data product needs its own reviewed policy record: source terms/authorization reference; allowed fields; classification and retention class; exact start event and field; primary clock and permitted fallback with rationale; approved duration/unit; provider deadline; refresh/duplicate semantics; derived-data, claim, export and cache treatment; backup/replica expiry and restore replay; hold authority/scope/review/release; policy owner, approver, effective date and immutable version.

A policy cannot activate with blank duration, unclear clock semantics, unknown provider terms, or unresolved backup behavior. 'Public data' is not itself a retention policy.

## 6. Decision procedure

1. Resolve exact data unit, source, version, and lineage.
2. Resolve classification, retention class, and immutable policy version; fail closed if absent.
3. Validate the specified start event and timestamp without substitution.
4. Evaluate provider obligations, mandatory deadlines, and exact-scope holds.
5. Calculate expiry only when all inputs are resolved.
6. At expiry, emit eligible_for_review; do not delete automatically.
7. Produce a payload-free dry-run manifest and require explicit authorization.
8. Execute separately approved transactional erasure and verify references, derived data, exports, caches, backups, replicas, and restore replay.
9. Record a minimal completion event only if policy permits; never copy erased payload into a tombstone.

## 7. Edge cases

- Repeated retrieval creates a new snapshot clock; it cannot extend older snapshots.
- Duplicate ingestion does not reset first-seen or source-version clocks.
- Provider timestamp changes are treated as a new source version, not a rewrite of old history.
- Missing publication time is unresolved unless policy explicitly defines retrieval time as the clock.
- Late-arriving data preserves event time and receipt time separately; policy selects the governing event.
- Clock skew/future timestamps are flagged, not silently clamped.
- Reassessment creates a new assessment clock and does not reset evidence or claim clocks.
- Relationship removal does not erase or extend evidence/claim lifecycle.
- Source erasure triggers lineage review for hashes, fingerprints, claims, exports, and caches.
- External exports cannot be claimed erased if their destination is outside CIN control.
- Backup restore must replay approved erasure records before restored data becomes queryable.
- Unknown provider terms block new collection/persistence pending review; they do not justify an automatic retention extension.

## 8. Acceptance gates

- [ ] Inventory provider endpoints/data products and verify source terms/authorization.
- [ ] Approve per-provider start event, timestamp, fallback, duration, and mandatory deadlines.
- [ ] Confirm current schema fields represent chosen events; otherwise design additive schema v2.
- [ ] Define first-seen/version/recorded timestamps without changing current timestamp meaning.
- [ ] Define duplicate, refresh, late-arrival, clock-skew, and reassessment behavior.
- [ ] Define lineage from snapshots to fingerprints, hashes, claims, relationships, exports, caches, and backups.
- [ ] Define holds, authority, review/release, and exception paths.
- [ ] Test expiry calculations with fixed clocks and policy versions, not wall-clock-dependent tests.
- [ ] Test missing/invalid clocks fail closed and re-ingestion never resets clocks.
- [ ] Test dry-run, authorization, idempotent erasure, residual scans, backup expiry, and restore replay.
- [ ] Obtain explicit approval before schema migration, worker activation, or production persistence.

## 9. Explicit non-actions and limitations

No retention durations, legal basis, provider authorization, provider terms, or legal-hold authority are asserted. No existing schema timestamp is redefined; no migration is created or applied; no existing record, observation, assessment event, fingerprint, or hash is changed or deleted. No expiry scheduler, deletion worker, hold mechanism, or production database is enabled. API remains read-only; SQLite remains a local reference adapter.

This is a technical design proposal, not legal advice or a compliance determination. F-05 is design-documented only; provider-specific policies and durations must be approved before implementation.