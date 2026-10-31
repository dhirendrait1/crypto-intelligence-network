# CIN Step 23 — F-03 Classification Implementation Readiness v1

**Status:** Pre-implementation readiness specification only. Not an approved policy, migration, or runtime control.  
**Current schema:** SQLite reference schema v1.0 remains unchanged.  
**Decision:** Do not implement classification/retention columns or backfill existing rows until the approval gates in this document are satisfied.

## 1. Objective

Translate the existing data-classification and retention-class proposal into a bounded implementation plan. This document identifies the exact data units, candidate schema shape, fail-closed behavior, migration sequence, and decisions that must be approved before code changes.

Classification and retention are separate dimensions. A classification answers how sensitive data is; a retention class selects a lifecycle policy. Neither label supplies a duration or authorizes collection, storage, access, or deletion.

## 2. Proposed field-level assignment matrix

These are candidate defaults for review, not active assignments.

| Data unit | Candidate classification | Candidate retention class | Required implementation boundary |
|---|---|---|---|
| Approved public provider snapshot | PUBLIC | SOURCE_TERMS_BOUNDED | Source-specific schema allowlist and provider permission |
| CIN evidence ID / namespace | INTERNAL | CLAIM_HISTORY_BOUNDED | Minimize external identifiers and restrict API exposure |
| External provider ID | PUBLIC or INTERNAL, source-dependent | SOURCE_TERMS_BOUNDED | Explicit source policy; treat as linkable |
| Observation timestamps/status | INTERNAL | SOURCE_TERMS_BOUNDED | Preserve observed/retrieved/published/checked distinctions |
| Metadata payload | PUBLIC only for approved fields | SOURCE_TERMS_BOUNDED | Reject unknown fields and prohibited data |
| Metadata fingerprint/content hash | INTERNAL | DERIVED_BOUNDED | Preserve source lineage and derivation purpose |
| Claim subject/predicate/statement/value | INTERNAL; CONFIDENTIAL if non-public | CLAIM_HISTORY_BOUNDED | Current public evidence path must reject confidential input |
| Relationship rationale | INTERNAL; CONFIDENTIAL if non-public | CLAIM_HISTORY_BOUNDED | Minimize free text; prefer evidence references |
| Assessment rationale | INTERNAL; reviewer identity separately governed | CLAIM_HISTORY_BOUNDED | No unauthenticated reviewer identity |
| Conflict records/links | INTERNAL | CLAIM_HISTORY_BOUNDED | Define dependency cleanup when source is erased |
| Sanitized operational diagnostics | INTERNAL | OPERATIONAL_SHORT_LIVED | No raw exception, payload, credential, or request headers |
| Exports/support bundles | Highest class of included data | No longer than source data | Export must inherit strictest classification and source expiry |
| Backups/replicas | Same as source | Same as source plus backup expiry | Restore-time erasure replay required |
| Erasure tombstone | INTERNAL | TOMBSTONE_MINIMAL | Opaque/minimal completion evidence only |
| Prohibited secrets | PROHIBITED | NOT_RETAINABLE | Reject before persistence; never hash, log, or export |

## 3. Candidate schema-v2 contract

A future additive schema may use a normalized policy registry rather than duplicating mutable policy text in every row.

Candidate fields on governed data units:
- `data_classification`: controlled enum.
- `retention_class`: controlled enum.
- `retention_policy_version`: immutable reference to an approved policy record.
- `retention_basis_at`: timestamp of the approved start event, not a substitute timestamp.
- `classification_source`: controlled provenance such as `source_schema`, `system_generated`, or `approved_operator`.

Candidate policy registry attributes:
- immutable policy version and status;
- source namespace / data-unit scope;
- approved purpose and minimum fields;
- classification and retention class;
- start-event definition and approved maximum age;
- source/provider terms reference and review date;
- legal/operational approval evidence reference;
- exception and legal-hold eligibility;
- deletion/redaction action and backup treatment;
- effective-from and supersession relationship.

Do not store free-form credentials, legal documents, reviewer secrets, or raw approval payloads in the policy registry. Store only controlled references and decision metadata approved for CIN.

## 4. Fail-closed runtime semantics

When eventually implemented:
1. Missing, unknown, malformed, or superseded policy reference must block persistence; no permissive default.
2. Unknown classification must be treated as the most restrictive handling state and rejected from the current public evidence flow.
3. Conflicting classifications resolve to the more restrictive class.
4. Combined data inherits the earliest applicable expiry obligation and highest classification.
5. Policy changes do not silently rewrite the policy version attached to historical rows.
6. A new policy version applies only according to an explicit effective-date and migration rule.
7. Expiry eligibility is not deletion authorization.
8. Legal hold can pause only a specifically approved scope, with authenticated authority, review, and release events.
9. Prohibited data is never retained under a legal-hold or exception class in this CIN scope.

## 5. Safe migration sequence

A separately reviewed migration should follow this sequence:
1. Freeze and document schema-v1 baseline and row counts.
2. Approve the policy registry schema and controlled vocabularies.
3. Define source-specific backfill rules for every existing row type.
4. Produce a dry-run backfill report listing every row that cannot be classified unambiguously.
5. Block migration if any row would receive a guessed or permissive policy.
6. Add schema-v2 fields/tables additively; do not alter append-only history semantics implicitly.
7. Backfill only rows covered by approved deterministic rules; quarantine unresolved rows without copying payloads.
8. Verify policy references, row counts, foreign keys, uniqueness, timestamps, and append-only triggers.
9. Test rollback, migration idempotency, policy immutability, and fail-closed writes.
10. Obtain explicit project approval before applying the migration to any persistent environment.

No backfill may infer source permission, legal basis, or retention duration from a timestamp or public availability.

## 6. Required acceptance tests before schema-v2 implementation

- Approved classification/retention vocabularies reject unknown values.
- Missing policy version blocks write.
- Unknown/superseded policy version blocks write.
- Policy registry versions are immutable.
- Source-specific policy scope is enforced.
- Combined fields inherit the strictest classification and earliest expiry.
- Existing schema-v1 rows receive only deterministic, approved assignments.
- Unresolved rows are reported and excluded from migration.
- Legal-hold authority, scope, review, release, and audit events are validated.
- Expiry eligibility never invokes deletion without separate authorization.
- Erasure dry-run, dependency cleanup, tombstone minimization, idempotency, rollback, backups, replicas, exports, caches, and restore replay are tested.
- Public API remains read-only unless a separate API write-path review is approved.

## 7. Approval register — unresolved

| Decision | Required approver/evidence | Current status |
|---|---|---|
| Classification vocabulary and prohibited-data handling | Explicit project policy approval | Not approved |
| Source-specific collection/retention permissions | Provider terms review and recorded source decision | Not approved |
| Applicable legal/privacy basis and jurisdictional requirements | Qualified legal/privacy review | Not approved |
| Numeric durations and start events | Approved policy owner decision per source/data unit | Not approved |
| Legal-hold authority and process | Authenticated governance/operational decision | Not approved |
| Schema-v2 field and policy-registry design | Technical design review | Proposal only |
| Existing-row backfill rules | Data inventory and deterministic mapping evidence | Not approved |
| Erasure, backup, export, restore workflow | Tested operational procedure and explicit approval | Not implemented |
| Production persistence activation | Separate explicit project approval | Not authorized |

No approval is inferred from the existence of this document, a passing CI run, or an open pull request.

## 8. Explicit non-actions

- No schema-v2 migration or SQL change is included.
- No classification or retention labels are written to existing rows.
- No retention durations, legal basis, provider permission, or hold authority are invented.
- No data is deleted, rewritten, exported, or backfilled.
- No retention scheduler, deletion worker, or API write path is enabled.
- No production database or deployment is changed.
- CIN remains read-only intelligence; no trading, wallet, credential, or fund-movement capability is introduced.

**Disposition:** F-03 is design-documented and implementation planning is now explicit. It remains open pending the approval register and separate schema-v2 implementation review. Step 23 remains Partial.
