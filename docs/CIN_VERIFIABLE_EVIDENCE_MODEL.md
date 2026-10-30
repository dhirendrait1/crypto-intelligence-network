# CIN Verifiable Evidence Model

## Status and purpose

This document defines a common evidence contract for future CIN research modules. It is a design specification, not a claim that all existing modules already implement this schema. Existing APIs may expose subsets of these fields and must retain their documented compatibility contracts until migrated deliberately.

The model separates a claim from the evidence records that support, contradict, qualify, or fail to address it. CIN records what a source says and what CIN observed; it does not convert source assertions into verified facts by default.

## 1. Core objects

### Claim

A claim is a bounded proposition that can be assessed against evidence.

Required fields:
- `claim_id`: stable CIN-generated identifier.
- `subject`: asset, protocol, issuer, contract, or other clearly scoped subject.
- `predicate`: controlled claim type (for example, reserve_quantity, redemption_right, protocol_fee_revenue, holder_concentration).
- `statement`: concise human-readable proposition.
- `value` and `unit`: typed value where the claim is quantitative; do not encode unknown as zero.
- `valid_time_start` / `valid_time_end`: period the claim purports to describe, where known.
- `created_at`: timezone-aware CIN record-creation time.
- `claim_status`: `supported`, `contradicted`, `mixed`, `insufficient_evidence`, or `not_assessed`.

A claim must not be more specific than its evidence. A claim about an issuer statement must be worded as an issuer statement, not as an independently established reserve fact.

### Evidence record

Each evidence record should contain:
- `evidence_id`: stable identifier within CIN; caller-supplied IDs must be explicitly marked as such until CIN assigns its own.
- `evidence_type`: document, provider observation, on-chain event, news article, social post, or analyst note.
- `source_name`, `source_url`, `source_role`, `source_role_authenticated`.
- `source_record_id`: provider or chain identifier where available.
- `published_at` / `observed_at`: source event/publication/observation time, with timezone.
- `retrieved_at`: CIN retrieval time, separate from source time.
- `valid_time_start` / `valid_time_end`: time period the evidence covers, where known.
- `content_hash`: optional hash of the exact retained content only when retention is permitted; a metadata fingerprint is not a content hash.
- `status`: `valid_metadata`, `stale`, `unavailable`, `invalid`, or `requires_review`.
- `limitations`, `missing_fields`, and `timestamp_validation_errors`.

Do not assume a source role from a hostname, URL path, social handle, or document title. If role authentication is unavailable, mark it false.

### Claim-evidence relationship

Each relationship records:
- `claim_id` and `evidence_id`.
- `relationship`: `supports`, `contradicts`, `qualifies`, or `context_only`.
- `rationale`: concise explanation of relevance.
- `review_status`: `automated_candidate`, `human_reviewed`, or `rejected`.
- `reviewed_at` and reviewer identity/type where permitted.

One evidence record may relate to multiple claims; one claim may have multiple supporting and contradicting records. Contradictions must remain visible and must not be hidden by selecting only favorable evidence.

## 2. Time semantics

Keep these timestamps distinct:

- **Published time:** when a publisher says an item was published.
- **Observed time:** when the underlying event or measurement occurred.
- **Provider-seen time:** when an index/provider says it first saw or indexed the item.
- **Retrieved time:** when CIN fetched the record.
- **Checked time:** when a reviewer or process last checked the source.
- **Valid time:** the period during which the claim/evidence is intended to apply.

Every supplied timestamp must retain its source semantics and validation status. Missing, timezone-naive, future-skewed, or impossible chronology must be surfaced; never silently substitute retrieval time for publication or observation time. Time-sensitive comparisons require aligned valid-time windows.

## 3. Source provenance and independence

- Preserve the original URL/record identifier and provider name.
- Normalize URLs only for duplicate identity; retain the submitted/display URL separately.
- A distinct hostname is not proof of independent ownership, authorship, audit, or corroboration.
- Source-role labels are self-reported unless a separate documented authentication method exists.
- Multiple copies of one press release or syndicated article are not independent evidence.
- Cross-source comparison must group the same metric and unit, apply an explicit time window and tolerance, and expose duplicate-source exclusions.
- If source independence cannot be established, report `source_independence_verified: false`.

## 4. Confidence and claim assessment

CIN must not express confidence as a numeric probability unless a calibrated model and validation dataset justify that interpretation.

Recommended descriptive evidence states:
- `insufficient_evidence`: too few valid or relevant records.
- `limited_support`: one or more relevant records, but source independence or authority is limited.
- `corroborated_support`: multiple demonstrably independent and relevant records support the same bounded claim.
- `conflicting_evidence`: credible records materially disagree.
- `stale_evidence`: evidence is outside the documented freshness policy.
- `unavailable_evidence`: required sources could not be retrieved.
- `not_assessed`: no assessment has been performed.

A descriptive state is not a truth guarantee. A source's self-reported `verified` label must never automatically become CIN's `corroborated_support`. Human review is not a substitute for documenting the underlying source and rationale.

## 5. Conflict handling

When evidence conflicts:
- Preserve every accepted record and its original claim.
- Report the conflicting values, units, valid-time windows, source roles, and timestamp quality.
- Identify duplicate/syndicated sources and whether independence is established.
- Use `manual_review_required` when the discrepancy cannot be resolved by a documented deterministic rule.
- Do not rank sources or choose a winner solely by recency, popularity, hostname, or an unauthenticated role label.
- Record any later resolution as a new review event; do not erase the historical conflict.

## 6. Freshness and completeness

Freshness thresholds must be specific to evidence type and metric; one global age threshold is not appropriate for all reserve attestations, market observations, audits, or governance documents.

Each assessment should expose:
- Applicable freshness policy and threshold.
- Evidence age and source-time semantics.
- Expected vs received source/record counts where measurable.
- Missing categories, missing time windows, scan gaps, and provider outages.
- Whether the result is complete, partial, stale, or unknown.

Missing evidence is unknown, not zero and not proof for or against a claim.

## 7. Auditability and versioning

- Preserve immutable assessment snapshots or append-only review events when persistence is implemented.
- Record schema version, methodology version, retrieval software version, and assessment time.
- Distinguish a metadata fingerprint from a content hash, digital signature, trusted timestamp, or source-authenticity proof.
- Never overwrite an earlier assessment without retaining its version and reason for change.
- Make source deletion, retention, licensing, and privacy obligations explicit before storing content.

## 8. Read-only and security boundaries

The model is for research and analysis only. It does not authorize trade/order execution, wallet control, private-key or seed-phrase handling, transaction signing/broadcasting, funds movement, personal deanonymization, or outbound social messaging.

## 9. Migration and acceptance

Existing commodity backing, growth fundamentals, public news, public evidence, cross-source comparison, and on-chain modules should adopt this contract incrementally. For each migration:

1. Map existing fields to the common semantics without relabeling source assertions as CIN verification.
2. Add schema and compatibility tests for missing, malformed, stale, future, duplicate, and conflicting evidence.
3. Preserve old response fields until a versioned API migration is approved.
4. Add deterministic fixtures proving claim/evidence links and timestamp semantics.
5. Document provider authorization, data rights, retention, and live-validation requirements.
6. Keep offline test evidence separate from authorized live-provider and deployed-service validation.

This specification does not assert that evidence is currently persisted, independently authenticated, or verified by CIN.
