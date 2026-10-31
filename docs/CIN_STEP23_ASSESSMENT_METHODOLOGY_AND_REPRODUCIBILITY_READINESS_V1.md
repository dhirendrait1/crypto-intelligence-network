# CIN Step 23 — Assessment Methodology and Reproducibility Readiness v1

**Status:** Readiness assessment and versioning contract only. No scoring formula, live provider behavior, or production assessment path changed.
**Scope:** Reproducing a historical assessment from its exact inputs, methodology, code, and policy versions.
**Boundary:** Read-only research and analysis; no trade execution, wallet control, signing, or fund movement.

## 1. Executive finding

The repository contains deterministic components and documented formulas, but no general reproducibility envelope that binds an assessment to an immutable input snapshot, method/configuration version, code revision, dependency set, provider response, and execution environment.

Observed examples:
- Coin screening documents a weighted heuristic (market cap 20, 24-hour volume 20, volume/market-cap 20, FDV gap 15, circulating/total supply 15, 24-hour price-change band 10). It also uses live provider responses, cache state, fallback provider data, and current timestamps; a repeated request is not guaranteed to use identical inputs.
- Commodity backing and growth fundamentals assess caller-supplied evidence metadata. Their default assessment clock uses current UTC time, and freshness classifications can therefore change between otherwise identical calls. Their metadata fingerprints are not immutable assessment snapshots.
- Cross-source comparison accepts explicit tolerances and a comparison window, but the caller must retain the exact input observations and parameters to reproduce a result.
- The shared claim identifier is deterministic for canonical claim identity, but is not a versioned assessment identifier or truth proof.

**Disposition:** Some calculation rules and deterministic primitives exist. End-to-end historical reproducibility, immutable input capture, and a common methodology registry remain unimplemented.

## 2. Reproducibility contract

A future assessment snapshot should bind the following, without silently substituting current values:

1. **Identity and scope:** assessment ID, subject/entity/instrument/contract/network, metric set, requested valid-time interval, quote currency/unit, venue and aggregation scope.
2. **Exact inputs:** canonical input records or permitted immutable references, source record IDs, source URLs, raw/normalized distinction, received order, exclusions, deduplication decisions, and missing-input markers.
3. **Source provenance:** provider/source namespace, source timestamps, retrieval timestamps, fallback use, cache age, response/schema version, and retrieval status.
4. **Methodology:** stable methodology ID, semantic version, effective date, formula/rules, weights, thresholds, tolerances, category mappings, rounding and null/missing-data behavior.
5. **Implementation:** repository commit, module/version, dependency lock or environment fingerprint, schema version, and relevant feature flags/configuration.
6. **Execution:** assessment time, explicit clock input, timezone, deterministic seed where relevant, locale/decimal behavior where relevant, and execution status.
7. **Output:** canonical result, component-level calculations, warnings, rejected inputs, limitations, completeness/freshness states, and output fingerprint.
8. **Lineage:** links from each output component to the exact input records and rules that contributed to it.

If source terms or privacy policy prohibit retaining raw content, retain only an approved immutable reference and sufficient permitted metadata. If the inputs cannot legally or technically be replayed, label the result non-replayable and explain why.

## 3. Methodology versioning rules

- Assign a stable ID and semantic version to each materially distinct assessment method.
- A patch version may correct implementation defects without intentionally changing the method; a minor version may add backward-compatible fields or optional diagnostics; a major version changes formulas, weights, scope, semantics, or missing-data treatment. Record the actual change regardless of version label.
- Store the exact method/configuration version with every assessment; never infer it from the current default.
- Maintain effective dates and a human-readable change log with reason, impact analysis, test evidence, and approval status.
- Never rewrite historical results when a method changes. Reassessment creates a new assessment linked to its predecessor.
- A backtest or historical rerun must identify whether it uses original source snapshots or revised provider data. Do not call a rerun an exact reproduction if source data changed.
- Keep heuristic scores, descriptive evidence states, coverage measures, and calibrated probabilities distinct.

## 4. Deterministic calculation requirements

For each method, specify and test:
- Canonical input ordering and stable tie-breaking.
- Duplicate identity and conflicting duplicate handling.
- Numeric types, finite-value validation, decimal precision, rounding mode and overflow behavior.
- Missing, null, zero, invalid, stale, partial and unavailable input semantics.
- Timezone, interval boundaries, timestamp skew and explicit clock behavior.
- Formula order, intermediate values, weights, thresholds and tolerance inclusivity.
- Provider fallback and cache provenance; fallback must never be silently mixed with primary-source values.
- Stable serialization and canonical output fingerprinting.
- Dependency and runtime versions for operations that can affect numerical or parsing results.

No missing value may silently become zero. Any imputation, interpolation, normalization or unit conversion must be an explicit, versioned method step with lineage and warnings.

## 5. Current implementation-specific reproducibility risks

| Area | Observed behavior | Reproducibility implication |
|---|---|---|
| Coin screening | Live market provider, fallback provider and cache paths; provider timestamps and retrieval state affect eligibility | Same query may use different inputs and data mode |
| Coin screening row cleanup | Duplicate provider IDs are collapsed by keeping the first row in provider input order | Provider row order is part of the effective input |
| Commodity backing | Default assessment clock is current UTC; default freshness threshold is 90 days | Freshness/status can change with assessment time |
| Growth fundamentals | Default assessment clock is current UTC; caller-selectable freshness threshold | Exact clock and threshold must be retained |
| Cross-source comparison | Caller-supplied observations, explicit tolerances and time window | Exact ordered input set and parameters are needed |
| Claim construction | Canonical identity fields are hashed deterministically | Stable claim ID does not capture method version or assessment inputs |
| Evidence fingerprints | Fingerprints cover selected normalized supplied metadata | Not a complete input snapshot, content hash, signature or replay proof |

This table describes the reviewed modules, not every CIN module or deployed runtime behavior.

## 6. Minimum reproducibility record

Before enabling persisted assessment history, define a versioned record with at least:
- assessment ID and predecessor/supersession link;
- subject and exact requested scope;
- input snapshot/reference and input fingerprint;
- coverage manifest/result and source provenance;
- methodology ID/version and canonical configuration fingerprint;
- code commit/module and schema versions;
- explicit assessment clock and execution environment fingerprint;
- output snapshot/fingerprint and component-level calculation trace;
- limitations, warnings, excluded inputs and non-replayable reasons.

Input/output fingerprints alone are insufficient: they do not replace the underlying permitted inputs, method definition, provenance, or lineage.

## 7. Acceptance tests before implementation

1. Identical canonical inputs, explicit clock, method version and configuration produce byte-stable canonical outputs.
2. Input row reordering either produces the same output or is explicitly declared semantically significant.
3. Duplicate IDs and conflicting duplicates follow a deterministic, documented rule.
4. Null, missing, zero, invalid, stale and unavailable values remain distinct.
5. Numeric boundaries, rounding, overflow and tolerance edges are deterministic.
6. UTC offsets and interval boundaries produce consistent results.
7. Provider fallback and cache paths retain distinct provenance and reproducible inputs.
8. Re-running a stored snapshot uses the original method version, not the latest default.
9. A method upgrade creates a new version and does not mutate historical output.
10. Reassessment after new source data links to, but does not overwrite, the previous assessment.
11. Input/output fingerprints match canonical serialized snapshots and are not treated as authenticity proof.
12. If raw inputs cannot be retained or retrieved, the system marks exact replay unavailable.
13. API and UI expose methodology version, data mode, source timestamps, missing inputs and limitations.
14. Independent test execution against a pinned environment reproduces the same result.

## 8. Gaps and dependencies

| Gap | Current disposition |
|---|---|
| Documented coin-screening weights | Exists; not a general versioned method registry |
| Versioned method/configuration registry | Not evidenced |
| Immutable assessment input snapshots | Not evidenced as a general facility |
| Explicit clock capture across modules | Some functions accept clock injection; common persisted contract absent |
| Pinned runtime/dependency fingerprint per assessment | Not evidenced |
| Component-level calculation trace and lineage | Not generally implemented |
| Stable canonical assessment output and fingerprint | Not evidenced as a common contract |
| Historical replay and method migration tests | Not evidenced end-to-end |
| Retention/permission for replay inputs | Depends on classification, provider governance and retention decisions |
| Persisted assessment snapshots | Depends on reviewed persistence and authorization implementation |

## 9. Explicit non-actions

No scoring weights, thresholds, provider priorities, source data, historical assessments, cache behavior, method defaults, runtime dependency, API, schema, scheduler, persistence wiring, deployment, Render/Cloudflare setting, or paid service was changed. No assessment was rerun or certified reproducible by this document.

**Disposition:** Methodology versioning and reproducibility requirements are documented. A common registry, immutable snapshot format, replay engine, and end-to-end reproducibility validation remain open. Step 23 remains Partial.
