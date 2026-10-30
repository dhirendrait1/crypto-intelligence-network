# CIN Step 23 — Claim/Evidence Migration Contract

## Scope

This is the first migration contract for the existing commodity-backing and growth-fundamentals assessment APIs. It is deliberately additive: existing request and response fields remain compatible, and no persistent store, source fetcher, authentication system, or new public API is introduced in this increment.

## Existing-field mapping

| Common evidence-model concept | Existing field or behavior | Current limitation |
|---|---|---|
| Evidence identity | `evidence_id` | Caller supplied; not CIN-authenticated or guaranteed globally unique |
| Evidence type / category | Commodity `evidence_type`; growth `category` | Module-specific vocabularies remain distinct |
| Source provenance | `source_name`, `source_url`, `source_role` | Role is self-reported; source identity is not authenticated |
| Publication time | `published_at` | Caller-supplied source metadata |
| Checked time | `checked_at` | Present in both normalized records; does not prove a source was actually checked by CIN |
| Claim statement | `claim_text` | Optional caller-supplied text; not independently validated |
| Change detection | `record_fingerprint_sha256` | Hashes normalized supplied metadata only, not source content or authenticity |
| Freshness | Existing assessment status and age fields | Module-specific thresholds and semantics remain in place |
| Claim identity | Additive `claim` object with deterministic `claim_id` | Created only from caller-supplied non-empty `claim_text`; status remains `not_assessed` |
| Relationship to a claim | Additive `claim_evidence_relationship` object | Created only when a caller-supplied `evidence_id` exists; always `context_only` and `automated_candidate` in this migration |

## Migration rules

1. Preserve all existing fields and endpoint behavior until a separately reviewed, versioned API change is approved.
2. Never treat caller-supplied `evidence_id`, `claim_text`, `source_role`, or `verified` status as CIN-authenticated facts.
3. Do not synthesize a claim-evidence relationship merely because a record contains a source URL. The current additive integration requires caller-supplied claim text and a stable evidence ID; it links them as `context_only` only and does not assert support.
4. Keep evidence identity separate from claim identity. One claim may have multiple evidence records; one evidence record may relate to multiple claims.
5. Keep published, observed, retrieved, and checked timestamps semantically distinct. Existing commodity/growth inputs do not yet provide a CIN retrieval timestamp.
6. Keep metadata fingerprints explicitly labeled as metadata-only; never expose them as content hashes, signatures, or authenticity proofs.
7. Preserve conflicts and missing evidence. Do not select a preferred source based only on recency, hostname, source-role label, or a caller-supplied status.
8. Do not add persistence or background collection until retention, deletion, licensing, privacy, and provider authorization requirements have been reviewed.

## Acceptance gates for subsequent increments

- Preserve the additive shared, versioned claim/evidence/relationship representation without changing legacy response fields.
- Keep stable CIN claim identifiers separate from evidence-record identity.
- Expand relationship types/review states only through separately reviewed evidence rules; current assessment integration must remain `context_only` / `automated_candidate` until source verification and human review exist.
- Validate duplicate IDs, missing claim text, malformed timestamps, stale records, and contradictory evidence with deterministic tests.
- Include schema/methodology version and timezone-aware CIN creation/retrieval timestamps only when those events actually occur.
- Add the shared module to the deployment scaffold and verify router/module registration in offline CI.
- Keep live-provider and deployed-service acceptance separate from offline tests.

## Current status

The assessment modules now expose additive first-class claim and relationship objects while preserving legacy fields. Claims remain `not_assessed`; relationships remain context-only traceability links. The increment does not persist evidence, fetch/authenticate source documents, or independently verify claims. Step 23 remains Partial.
