# CIN Step 23 — Claim Conflict Resolution and Review-State Readiness v1

**Status:** Repository-level implementation/readiness assessment. No claim adjudication engine, reviewer identity system, API, or persistence activation.
**Scope:** Shared claim/evidence primitives and the common verifiable evidence model.
**Boundary:** Research and analysis only; no trade execution, wallet control, signing, or fund movement.

## 1. Executive finding

The common evidence specification defines distinct claim and evidence objects, four relationship types, descriptive evidence states, and a conflict-handling policy that preserves contradictory records and requires manual review when deterministic resolution is unavailable. The current shared Python primitives construct deterministic claim IDs and validate relationship type, rationale, review-status vocabulary, and timestamps.

The primitives do not implement a conflict detector, evidence comparability engine, source-independence evaluator, reviewer identity/authentication, review authorization, assessment state machine, or persisted append-only review history. The human_reviewed value is currently a caller-supplied label in an in-memory relationship object; it is not proof that an authenticated human reviewed the evidence.

**Disposition:** Object construction and vocabulary validation exist. Conflict detection, adjudication, authenticated review, and durable resolution history remain unimplemented.

## 2. Existing implementation and specification

| Capability | Current evidence | Assessment |
|---|---|---|
| Stable claim identity | Canonical claim fields hashed into a deterministic ID | Implemented as an identity aid, not truth proof |
| Relationship vocabulary | supports, contradicts, qualifies, context_only | Validated by shared primitive |
| Review-status vocabulary | automated_candidate, human_reviewed, rejected | Validated as an enum only |
| Rationale and timestamps | Required rationale; timezone-aware creation timestamp | Basic construction validation |
| Conflict preservation | Specification says retain all accepted supporting and contradicting records | Design requirement; no conflict repository/API demonstrated |
| Comparability | Specification requires same metric/unit/time window and source independence checks | No general comparison engine demonstrated |
| Manual review | Specification calls for manual review when deterministic resolution is unavailable | No executable workflow/state transition demonstrated |
| Reviewer identity | Specification anticipates reviewer identity/type where permitted | Not authenticated by primitive |
| Resolution history | Specification requires new review event and preservation of historical conflict | No review-event API/store demonstrated |

The shared primitive explicitly marks relationships as not persisted. Its review-status value is not an authorization or identity assertion.

## 3. Required conflict lifecycle

A future conflict workflow should use explicit, non-destructive states:

1. **Candidate:** evidence is linked to a claim but relevance/comparability is not yet established.
2. **Comparable:** entity, metric, unit, scope, valid-time window, and timestamp semantics have passed metric-specific checks.
3. **Conflict detected:** comparable records materially disagree under an approved metric-specific tolerance.
4. **Manual review required:** source authority, independence, methodology, or discrepancy cannot be resolved deterministically.
5. **Reviewed — unresolved:** reviewer records findings but no defensible winner is selected.
6. **Resolved under policy:** a versioned, approved rule explains the disposition and its limitations.
7. **Superseded/reopened:** new evidence or a source revision requires a new review event; previous events remain available.

Do not use a single mutable status field as the only record of this lifecycle. Persist append-only review events with previous state, new state, reason, policy/methodology version, event time, reviewer identity/type, and linked evidence IDs. Authentication and authorization must be enforced outside the caller-supplied payload.

## 4. Comparability gate before conflict detection

A numeric difference is not automatically a conflict. Before comparison, require:

- same canonical subject/instrument/contract/network;
- same predicate/metric definition;
- compatible units, denomination, precision, and conversion method;
- same venue or explicitly compatible aggregation scope;
- aligned valid-time intervals and timezone-aware timestamps;
- source-specific freshness and timestamp-quality checks;
- methodology/version compatibility;
- duplicate/syndicated-source and upstream-dependency assessment.

If any required dimension is missing or incompatible, classify the pair as incomparable or unknown, not conflicting. Do not infer a value of zero from missing evidence.

## 5. Resolution and confidence safeguards

- Never select a winner solely by recency, popularity, hostname, unauthenticated source role, or provider ranking.
- Never average conflicting values unless a metric-specific aggregation method explicitly requires it and its assumptions are documented.
- Preserve both source assertions and their original provenance.
- Distinguish source assertion, automated candidate, human reviewed, and CIN's own assessment.
- Do not promote human review to truth or source authentication.
- Use descriptive evidence states; do not emit numeric probabilities without calibrated validation.
- A resolution must cite the policy/methodology version and state what it does not establish.
- New evidence must create a new assessment/review event; it must not overwrite the earlier conflict.

## 6. Minimum implementation acceptance tests

Before activating a conflict workflow, require tests for:

- Supporting and contradicting records coexist for one claim.
- Same metric with different units, entities, venues, or time windows is marked incomparable.
- Duplicate/syndicated sources are not counted as independent corroboration.
- Missing/naive/future/out-of-order timestamps block unsafe comparison.
- Stale, partial, unavailable, and malformed evidence cannot silently become current or zero.
- Tolerance boundaries are metric-specific, versioned, and deterministic.
- A conflict requires manual review when no approved deterministic rule applies.
- Caller cannot self-assert authenticated reviewer identity or bypass authorization.
- Review transitions reject invalid or unauthorized state changes.
- Resolution appends a new event and preserves the original conflict and prior review events.
- Reassessment after new evidence does not mutate historical snapshots.
- API and storage failures do not return false resolved or verified statuses.
- Provenance, limitations, policy version, and reviewer identity/type survive serialization and retrieval.

## 7. Gaps and implementation dependencies

| Gap | Required dependency |
|---|---|
| Conflict detector and comparability engine | Metric definitions, canonical units/entities, approved tolerances |
| Source independence evaluation | Provider registry, ownership/upstream lineage, duplication rules |
| Authenticated human review | F-09 access-control and authorization implementation |
| Append-only review event storage | Evidence persistence integration and schema review |
| Review queue and escalation | F-11 observability/incident ownership and approved reviewer roles |
| Resolution policy versioning | Provider governance and metric-specific methodology approval |
| API exposure | Versioned API contract, authorization, privacy and error-boundary review |
| End-to-end validation | Offline deterministic suite plus separately authorized live validation |

## 8. Explicit non-actions

No claim was adjudicated. No evidence status, review status, or source role was promoted. No conflict detector, scoring model, reviewer account, authorization rule, queue, endpoint, schema migration, persistence wiring, deployment, Render/Cloudflare setting, or paid service was added. No historic evidence was changed or deleted.

**Disposition:** Conflict lifecycle requirements and acceptance gates are documented. Detection, authenticated review, resolution, and persisted history remain unimplemented. Step 23 remains Partial.
