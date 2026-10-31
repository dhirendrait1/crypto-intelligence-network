# CIN Step 23 — Derived Hash and Fingerprint Lifecycle v1

**Status:** Design-only proposal; no independent hash retention is approved.
**Scope:** Metadata fingerprints, optional content hashes, and future derived indicators linked to evidence.
**Compatibility:** SQLite schema v1.0 and existing records remain unchanged.

## 1. Current implementation facts

- The local SQLite adapter canonicalizes allowlisted metadata as JSON and computes SHA-256 over the UTF-8 serialized metadata.
- The resulting metadata fingerprint is stored on each observation as metadata_fingerprint_sha256.
- The reference schema includes content_hash_sha256, but the current adapter writes NULL for this field; no content-byte hashing workflow is implemented here.
- The fingerprint supports normalized-metadata equality/deduplication analysis. It does not prove source identity, authenticity, truth, integrity of a provider, or independent verification.
- A deterministic unkeyed hash can remain linkable across observations and can confirm a guessed/known candidate payload. It must not be labelled anonymous merely because the original payload is absent.
- Derived indicators are not assumed to exist in the current persistence path. Any future indicator must declare its source lineage and transformation version.

## 2. Data classification and default lifecycle

Treat fingerprints, content hashes, and derived indicators as derived data, not automatically public or anonymous data. Their classification must be no lower than the most restrictive applicable source/inputs unless a documented review justifies a different classification.

Default rule: a derived item inherits the source data's retention class, policy version, and expiry basis. Its expiry must be no later than the earliest applicable source expiry. If it depends on multiple sources, it must not outlive the earliest-expiring required input unless an independently approved policy explicitly authorizes that outcome.

Source erasure, provider deletion requirements, or a valid hold/release decision must trigger a lineage review of all derived items. The default action is to delete or recompute the derived item as part of the same controlled erasure scope; do not retain it simply because it is a short hash.

## 3. Lineage requirements

Every future derived item must be traceable to:

- the exact source evidence and observation/version IDs;
- the source namespace and applicable policy version;
- the transformation or fingerprint algorithm identifier and version;
- the derivation timestamp and purpose;
- the complete set of input IDs for multi-source indicators;
- the derived item's classification and retention class;
- its expiry basis and any separately approved independent-retention decision.

Missing or ambiguous lineage means the item is not eligible for independent retention. Do not reconstruct lineage from matching hash values or timestamps.

## 4. Fingerprint-specific controls

1. Use the fingerprint only for the documented equality/deduplication purpose; do not repurpose it as a user, wallet, device, or cross-project tracking identifier.
2. Keep algorithm and canonicalization versions explicit. A canonicalization change creates a new fingerprint version; never silently reinterpret old values.
3. Avoid exposing fingerprints in public API responses, URLs, analytics labels, or logs unless a separately reviewed use case requires it.
4. Do not treat deterministic equality as evidence that two provider records are authentic, independent, or factually equivalent.
5. Do not create a secondary index or cross-source correlation use without a documented purpose, privacy review, and approval.
6. When source metadata is erased, erase its fingerprint by default. A fingerprint may remain only under the independent-retention gate below.

## 5. Content-hash-specific controls

1. Compute a content hash only for exact bytes CIN is authorized to retrieve and process; do not fetch arbitrary URLs or retain content solely to calculate a hash.
2. Record the exact content version, byte representation, algorithm, derivation time, and source lineage. Distinguish raw bytes from normalized text or transformed representations.
3. A content hash proves only byte equality for the specified representation; it does not prove who published the content or whether the content is true.
4. A hash of predictable or publicly available content may be tested against candidate content. Treat it as potentially linkable and potentially revealing.
5. When source bytes must be erased, the hash expires with them by default. Retaining only the hash is not a substitute for source deletion obligations.

## 6. Future derived indicators

Any future score, aggregate, feature, or indicator derived from evidence must retain a machine-readable lineage set and transformation version. If the indicator cannot be traced to its inputs, it must not be presented as independently reproducible or retained after source erasure by default.

Aggregates may be considered for independent retention only after review demonstrates that they do not expose or permit practical inference of erased source data, are not linkable to a person or restricted source, and serve a separately approved purpose. Small cohorts, rare events, unique values, and differencing across repeated aggregates require explicit consideration.

## 7. Narrow independent-retention exception

Independent retention is an exception, not the default. All conditions below must be satisfied and recorded in an immutable policy version:

1. A specific, necessary purpose distinct from convenience, debugging, or indefinite audit accumulation.
2. A documented source/provider permission and applicable legal/privacy basis for retaining the derived item after source expiry or erasure.
3. A privacy/re-identification and known-content confirmation assessment appropriate to the hash/indicator type.
4. Evidence that the item cannot reasonably reconstruct, identify, link to, or confirm the erased source beyond the approved residual risk.
5. No provider contract, deletion obligation, valid erasure requirement, or other mandatory rule requiring the derived item to be removed.
6. A separately approved classification, retention class, start event, duration, access rule, and expiry process.
7. Explicit lineage, accountable policy owner, approval evidence, effective date, and review trigger.

If any condition is unknown, contradictory, or unsupported, fail closed: erase with the source through the approved workflow or keep the item quarantined from use pending a decision. Do not assume a plain SHA-256 digest qualifies for this exception.

## 8. Erasure dependency procedure

1. Resolve the source evidence/version and all direct and transitive derived descendants using recorded lineage.
2. Generate a dry-run manifest containing opaque IDs, derivation types, policy versions, and intended actions; exclude payloads and raw hashes from general-purpose reports.
3. Apply exact-scope holds and independently approved exceptions. A hold on one source does not automatically hold unrelated inputs or outputs.
4. Default to removing fingerprints, hashes, and indicators whose source is erased, unless every independent-retention condition is approved.
5. Remove or deactivate dependent references, caches, exports, and replicas under the approved retention workflow; identify external copies outside CIN control as unresolved.
6. Verify primary-store, index, cache, export, backup, replica, and restore-path postconditions.
7. Record only a permitted minimal completion event. Do not copy the erased payload or a disallowed hash into the tombstone.
8. Report partial completion explicitly; never label the whole lineage erased while a controlled copy remains.

## 9. Acceptance gates for future implementation

- [ ] Inventory every persisted or emitted fingerprint/hash and its exact purpose.
- [ ] Confirm algorithm, canonicalization, representation, and version semantics.
- [ ] Add explicit lineage from each derived item to source observation/version IDs.
- [ ] Define multi-source dependency and earliest-expiry propagation.
- [ ] Add tests proving source expiry/erasure reaches derived descendants, caches, exports, and backup restore.
- [ ] Add tests for ambiguous/missing lineage failing closed.
- [ ] Review linkability, known-content confirmation, small-cohort inference, and public exposure.
- [ ] Approve any independent-retention exception with source permissions, purpose, policy version, duration, and review evidence.
- [ ] Obtain explicit project approval before schema migration, API exposure, background processing, or production persistence.

## 10. Explicit non-actions and limitations

No current fingerprint or hash is modified or deleted. No content-hash computation is added. No derived-indicator pipeline, lineage table, schema migration, API exposure, retention worker, or production persistence is implemented. SQLite schema v1.0 remains unchanged, the API remains read-only, and the adapter remains local-only.

This document is a technical design proposal, not legal advice, a de-identification certification, or a claim that hashes are anonymous. F-07 is design-documented only; implementation remains blocked pending policy approval and a separately reviewed schema version.