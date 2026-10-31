# CIN Step 23 — Data Classification and Retention Classes v1

**Status:** Design proposal only; not an approved legal/privacy policy and not runtime enforcement.  
**Schema baseline:** SQLite reference schema v1.0 remains unchanged.  
**Scope:** Step 23 evidence records, observations, claims, relationships, assessment events, conflicts, provenance, metadata fingerprints, content hashes, operational diagnostics, exports, backups, and replicas.  
**Safety boundary:** CIN remains read-only intelligence. This design does not authorize trade execution, wallet access, fund movement, credential collection, or production persistence.

## 1. Purpose and governing rules

This specification separates two decisions that must not be conflated:

- **Data classification** describes the sensitivity and handling requirements of a value.
- **Retention class** identifies the lifecycle rule family that must govern that value. A retention class is not a retention duration.

No retention duration, legal basis, jurisdictional conclusion, source licence, or deletion exception is inferred here. Those require explicit provider, operational, and legal review before implementation.

Rules:

1. Collect and retain only fields needed for a documented CIN intelligence purpose.
2. Reject prohibited secrets and unrelated sensitive data at the boundary; do not create a class that permits retaining them.
3. Keep caller assertions, CIN observations, provider-retrieved values, and human-review decisions distinguishable.
4. Apply classification and retention metadata at the smallest practical data unit; do not assume an entire record has one uniform sensitivity.
5. When multiple values are combined, apply the most restrictive classification and the earliest applicable retention obligation.
6. Derived hashes and fingerprints remain potentially linkable data; they are not automatically anonymous.
7. Append-only history is an integrity mechanism, not an exemption from approved retention or erasure requirements.
8. Unknown or unclassified data must not silently inherit a permissive policy.

## 2. Classification vocabulary

| Class | Meaning | Required handling |
|---|---|---|
| PUBLIC | Information already intentionally public and approved for the stated CIN use | Preserve source attribution, terms, timestamps, and provenance; public availability does not waive provider restrictions |
| INTERNAL | CIN-generated operational metadata or analysis not intended as a public source assertion | Limit access to project components and users who need it; avoid exposing internal diagnostics |
| CONFIDENTIAL | Non-public business, reviewer, or user-supplied information whose disclosure could cause harm | Minimize collection; restrict access; do not expose in public API responses or general logs |
| RESTRICTED | Highly sensitive data that requires exceptional controls and an explicit approved purpose | Default deny; CIN v1 evidence scope should not collect or persist this class |
| PROHIBITED | Credentials, authentication secrets, private keys, seed/recovery phrases, wallet secrets, payment secrets, or unrelated highly sensitive personal data | Reject; do not persist, log, hash, export, or send to external scanning services |

**Default rule:** approved public provider metadata may be PUBLIC; CIN-generated identifiers, fingerprints, status labels, and diagnostics are normally INTERNAL; non-public reviewer notes or user-supplied confidential material are CONFIDENTIAL and should not be accepted into the current public evidence flow. RESTRICTED is deny-by-default. PROHIBITED is never a storage class.

## 3. Proposed retention-class vocabulary

These are policy selectors, not time periods. Each requires a separately approved policy version with a start event, maximum age, permitted exceptions, deletion action, and backup treatment.

| Retention class | Intended data | Required lifecycle semantics |
|---|---|---|
| SOURCE_TERMS_BOUNDED | Provider-supplied metadata and any authorized source-derived content | Start from the actual retrieval/receipt event defined by provider terms; enforce the stricter of provider terms and approved CIN policy |
| DERIVED_BOUNDED | Metadata fingerprints, content hashes, normalized values, computed indicators | Document derivation purpose and linkability; retention cannot outlive source data automatically |
| CLAIM_HISTORY_BOUNDED | Claim statements, relationships, conflict references, assessment rationales | Start from the approved claim/assessment lifecycle event; preserve only while the audit purpose remains justified |
| OPERATIONAL_SHORT_LIVED | Request diagnostics, transient processing metadata, temporary exports | Use a separately approved operational schedule; never log payloads, credentials, or raw provider bodies |
| LEGAL_HOLD_CONTROLLED | Specific records subject to a valid, authenticated hold | Suspend only the approved deletion scope; record hold authority and review/release events outside payload data |
| TOMBSTONE_MINIMAL | Minimal proof that an approved erasure action was completed | Retain only where lawful and necessary; no erased payload, raw identifier, or reversible content |
| NOT_RETAINABLE | Prohibited data and data without an approved purpose or lawful/provider basis | Reject at ingestion; if discovered later, quarantine and follow an approved incident/erasure process |

No class is assigned a numeric duration in this version. A policy cannot be activated until duration, start event, exceptions, authority, and backup expiry are approved.

## 4. Proposed data-unit mapping

| Data unit | Default classification | Proposed retention class | Notes / constraints |
|---|---|---|---|
| Public provider metadata snapshot | PUBLIC | SOURCE_TERMS_BOUNDED | Source-specific allowlist and provider terms govern |
| CIN evidence record ID and source namespace | INTERNAL | CLAIM_HISTORY_BOUNDED | Keep external identity only when needed; avoid unnecessary raw identifiers |
| External provider evidence ID | PUBLIC or INTERNAL according to source | SOURCE_TERMS_BOUNDED | Treat as linkable; namespace it and minimize exposure |
| Observation timestamps and source status | INTERNAL | SOURCE_TERMS_BOUNDED | Preserve distinct observed/retrieved/published/checked semantics |
| Metadata JSON payload | PUBLIC only for approved public fields; otherwise reject from current flow | SOURCE_TERMS_BOUNDED | No arbitrary payloads or full document mirroring |
| Metadata fingerprint | INTERNAL | DERIVED_BOUNDED | Can confirm known content; erase or retain only under explicit purpose |
| Content hash | INTERNAL | DERIVED_BOUNDED | Only for authorized bytes; hash is not authenticity proof or anonymization |
| Claim subject, predicate, statement, typed value | INTERNAL by default; CONFIDENTIAL if non-public input | CLAIM_HISTORY_BOUNDED | Avoid personal data and copied confidential source text |
| Relationship rationale | INTERNAL; CONFIDENTIAL if non-public | CLAIM_HISTORY_BOUNDED | Prefer evidence references over copied source passages |
| Assessment rationale and methodology version | INTERNAL; reviewer identity data is separately restricted | CLAIM_HISTORY_BOUNDED | No unauthenticated reviewer identity claims |
| Conflict metadata and observation links | INTERNAL | CLAIM_HISTORY_BOUNDED | Preserve disagreement only while justified; remove misleading active links after approved erasure |
| Operational errors and logs | INTERNAL | OPERATIONAL_SHORT_LIVED | Sanitized categories only; no secrets, raw payloads, headers, or full exception bodies |
| Export files and support bundles | Highest classification of included data | Same as source data, or stricter | No export may extend source retention by default |
| Backups and replicas | Same as source data | Same class plus backup-expiry rule | Erasure must be reconciled through backup rotation and restore replay |
| Legal hold record | INTERNAL or CONFIDENTIAL | LEGAL_HOLD_CONTROLLED | Hold authority and scope must be authenticated and auditable |
| Erasure tombstone | INTERNAL | TOMBSTONE_MINIMAL | Opaque reference and minimum completion facts only |

If classification is uncertain, do not downgrade. Reject, quarantine without copying the payload, or request an approved schema/policy decision.

## 5. Policy-version contract for a future schema

A future schema version may add explicit fields or normalized policy references. This is a proposal, not a migration:

- `data_classification`: controlled enum from Section 2, assigned at field/record boundary.
- `retention_class`: controlled enum from Section 3.
- `retention_policy_version`: immutable identifier for the approved rule set applied at ingestion.
- `retention_basis_at`: timestamp for the approved retention start event; never substitute a different timestamp silently.
- `legal_hold_state`: explicit state only if a governed hold workflow is approved; no free-form boolean without authority and audit.
- `classification_source`: controlled provenance such as source_schema, system_generated, or approved_operator; never infer an operator identity.

The schema must define behavior for missing, unknown, conflicting, and superseded policy versions. A record must not be assigned a permissive fallback when policy lookup fails. Policy versions used by existing rows must remain resolvable for audit.

## 6. Retention decision and erasure lifecycle

Before implementation, each source/data class must have an approved policy record specifying:

1. Purpose and minimum required fields.
2. Provider authorization/licence and any provider-imposed deletion or retention requirement.
3. Classification and retention class.
4. Retention start event and maximum duration.
5. Legal-hold eligibility, authority, scope, review, and release.
6. Deletion/redaction/pseudonymization action for payloads, derived data, relationships, conflicts, exports, caches, logs, backups, and replicas.
7. Required tombstone fields and justification.
8. Verification query, exception reporting, backup expiry, and restore-time replay.
9. Policy owner, approval evidence, effective date, and version.

A future controlled erasure process must use dry-run manifests, explicit approval, transaction-safe changes, postcondition checks, idempotent retries, and backup/restore verification. It must not expose a general-purpose delete method or silently disable v1.0 append-only triggers.

## 7. Schema v1.0 compatibility and explicit non-actions

- No v1.0 SQL table, column, index, or trigger is changed by this document.
- No migration is added or applied.
- No classification or retention class is written into existing rows.
- No record, observation, assessment event, hash, or fingerprint is deleted or rewritten.
- No retention duration, legal basis, or legal-hold authority is invented.
- No retention worker, scheduler, API write path, or production database is enabled.
- The public evidence API remains read-only; local SQLite remains an explicit reference adapter.

## 8. Acceptance gates for a future implementation

- [ ] Approve classification vocabulary, source-specific defaults, and prohibited-data handling.
- [ ] Approve retention classes, exact durations, start events, exceptions, and policy ownership per source/data type.
- [ ] Review provider terms and applicable privacy/legal requirements.
- [ ] Define schema-v2 migration and policy-version backfill for existing records without guessing.
- [ ] Define field-level inheritance and conflict-resolution rules.
- [ ] Test missing/unknown policy fail-closed behavior and policy-version immutability.
- [ ] Test legal holds, dry runs, idempotent erasure, transaction rollback, tombstones, and dependency cleanup.
- [ ] Test exports, logs, caches, backups, replicas, restore replay, and residual-data verification.
- [ ] Obtain explicit project approval before implementation or production activation.

## 9. Known limitations

This document is a design proposal, not legal advice, a privacy impact assessment, a security certification, or evidence of compliance. It does not decide whether a particular source may legally be collected or retained. The conservative secret-pattern screening in the local adapter is not comprehensive DLP and cannot reliably classify arbitrary text. Classification and retention labels alone do not enforce access controls, encryption, deletion, backup expiry, or API authorization.

**Disposition:** F-03 has a documented design proposal. It remains open for policy approval and future schema implementation. F-05 and F-07 remain open until source-specific retention semantics and derived-data lifecycle decisions are approved.
