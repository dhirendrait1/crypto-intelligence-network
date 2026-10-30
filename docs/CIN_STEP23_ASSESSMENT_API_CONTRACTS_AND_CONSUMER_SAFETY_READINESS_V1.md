# CIN Step 23 — Assessment API Contracts, Output Integrity and Consumer Safety Readiness (F-19)

**Status:** Contract/readiness design only  
**Date:** 2026-10-31  
**Scope:** Coin screening, commodity-backing assessment, growth-fundamentals assessment, and cross-source evidence comparison.

## 1. Purpose and safety boundary

F-19 defines a consistent consumer-facing contract for CIN assessment outputs. A dashboard or API consumer must be able to distinguish the subject assessed, inputs and sources, observation/retrieval times, freshness, coverage, methodology identity, uncertainty, limitations, and whether a statement is merely caller-supplied.

This is an API and research-integrity design. It does not certify assets, issuers, reserves, source documents, or investment merit. It does not create trade execution, order routing, wallet control, or fund movement. No runtime implementation or deployment is part of this readiness increment.

## 2. Current repository evidence

Reviewed:
- `commodity_backing_api.py` and `tests/test_commodity_backing_api.py`
- `growth_fundamentals_api.py` and `tests/test_growth_fundamentals_api.py`
- `cross_source_evidence_api.py` and `tests/test_cross_source_evidence_api.py`
- `coin_screening_step2.py` and the existing coin-screening tests
- module documentation for commodity backing and growth fundamentals.

Existing controls include Pydantic request models with extra fields forbidden, bounded evidence batches and text fields, strict integer freshness/window controls, finite-number checks, explicit read-only/source-fetch boundaries, and regression tests for important validation cases. Commodity and growth endpoints explicitly label evidence as caller-supplied metadata and state that CIN did not fetch source documents. Cross-source comparison states it does not select a preferred source and is not a certification. Coin screening carries provider/fallback metadata, quote currency, freshness and eligibility holds in its output path.

The reviewed modules do not yet expose one shared, versioned response envelope with consistently required assessment identity, methodology version, input snapshot identity, explicit assessment clock, coverage/completeness, source provenance, limitations, and machine-readable uncertainty semantics. Current output shapes and safety flags are module-specific. A supplied `verified` evidence status is caller metadata and must never be rendered as CIN-verified without independent authentication.

## 3. Contract design principles

1. **Stable envelope:** all assessment endpoints return a predictable common outer structure while preserving module-specific detail under a typed result object.
2. **Additive evolution:** optional fields may be added compatibly; breaking semantic changes require an explicitly versioned contract.
3. **No silent defaults:** omitted, null, zero, unknown and unavailable have distinct meanings.
4. **Provenance travels with claims:** each material result can be traced to its inputs and source references.
5. **Freshness is explicit:** distinguish source observation time, publication time, provider retrieval time, cache time and CIN assessment time.
6. **Uncertainty is first-class:** partial, stale, conflicting, unavailable, unknown and not-assessed are not collapsed into a single success state.
7. **Safe language:** caller-supplied metadata, heuristic classification, source-reported claims and independently verified facts are visually and semantically distinct.
8. **No false confidence:** a heuristic score or evidence coverage percentage is not a probability, certification, quality score or expected return.
9. **Read-only contract:** endpoints must not imply that assessment triggers an external action or writes persistent state unless a separately approved contract explicitly says so.
10. **Bounded exposure:** request and response sizes, pagination, URL display, free text, and error detail remain constrained.

## 4. Proposed common response envelope

A future response should use a stable structure similar to the following. This is a conceptual contract, not an implemented schema:

```json
{
  "contract_version": "1.0",
  "assessment_id": "opaque-stable-id",
  "assessment_type": "coin_screening",
  "subject": {
    "entity_id": "provider-or-CIN-entity-id",
    "symbol": "BTC",
    "display_name": "Bitcoin",
    "identity_status": "provider_mapped"
  },
  "status": "complete",
  "assessment_clock": "2026-10-31T00:00:00Z",
  "methodology": {
    "methodology_id": "coin-screening",
    "version": "1.0.0",
    "code_revision": "commit-sha",
    "configuration_fingerprint": "sha256:..."
  },
  "input_provenance": {
    "source_mode": "provider_retrieved",
    "sources": [],
    "snapshot_id": null,
    "retrieved_at": null,
    "observed_at": null,
    "fallback_used": false
  },
  "coverage": {
    "status": "partial",
    "expected": null,
    "observed": null,
    "missing": [],
    "not_assessed": []
  },
  "uncertainty": {
    "level": "unknown",
    "reasons": []
  },
  "limitations": [],
  "result": {},
  "warnings": [],
  "read_only": true
}
```

The example values are illustrative only. Do not emit placeholder IDs, invented timestamps, or fabricated counts. Fields that cannot be established must be null or explicitly unknown/not_assessed according to the schema; they must not be inferred from retrieval time or UI defaults.

## 5. Required semantics

### 5.1 Identity and scope
- Identify the asset/entity using a stable CIN identifier where available and retain provider-native identifiers separately.
- Symbol alone is not a unique identity. Include chain/network, contract address or provider identity where applicable and permitted.
- State quote currency, unit, metric period and entity scope for numeric values.
- If identity resolution is ambiguous, return an explicit ambiguous/unresolved state and hold dependent conclusions.

### 5.2 Time fields
Keep distinct:
- `published_at`: when the source says the material was published;
- `observed_at`: time the source measurement applies to;
- `retrieved_at`: when CIN or the caller retrieved it;
- `checked_at`: when evidence metadata was checked;
- `assessment_clock`: the fixed clock used for freshness and calculations.

Timestamps must be timezone-aware, normalized consistently, and validated for impossible ordering. Missing or malformed source times remain unknown; the API must not substitute the current time. Cache age and source-data age must be represented separately.

### 5.3 Provenance
For each source reference, retain source name/namespace, source-native ID where available, URL or permitted reference, source role and whether the role is authenticated, source mode (caller-supplied/provider/cache/fallback), retrieval/observation timestamps, quote/unit context, freshness, and mapping/normalization caveats.

A URL, hostname, source label, caller-provided role, hash, or `verified` string is not proof of source identity, ownership, independence, document integrity, or truth. Fingerprints are change-detection aids, not signatures.

### 5.4 Status, coverage and uncertainty
Use distinct status vocabularies with documented transitions:
- assessment status: complete, partial, stale, unavailable, unknown, not_assessed, failed;
- evidence status: verified (only when the verification authority and method are explicit), unverified, stale, unavailable, conflicting, not_assessed;
- identity status: resolved, provider_mapped, ambiguous, unresolved;
- uncertainty: low, moderate, high, unknown only where a defined methodology supports the classification; otherwise expose reasons without inventing a confidence class.

Coverage must state its denominator or explicitly say it is unavailable. A percentage must not be emitted if expected coverage is unknown. Missing evidence is not negative evidence. Abstention and exclusions must be visible.

### 5.5 Scores and interpretations
- Distinguish heuristic score, evidence coverage, source agreement, and probabilistic forecast.
- Return score definition, range, component contributions, exclusions and methodology version when applicable.
- Do not label heuristic scores as confidence or probability.
- Cross-source agreement is limited corroboration only when source independence and metric comparability are established; otherwise show the limitation.
- Commodity evidence status does not certify backing or redemption.
- Growth evidence coverage does not measure project quality or future returns.

## 6. Module-specific response requirements

### Coin screening
Expose provider and fallback attribution, quote currency, source observation time, retrieval/cache time, freshness status, scan universe/coverage where actually known, duplicate/invalid identity accounting, asset-type heuristic caveat, component score contributions, excluded/held status and reasons. A stale/unknown timestamp or incomplete critical metric must not be rendered as a clean candidate signal.

### Commodity-backing assessment
Keep issuer/custodian/auditor claims separate from authenticated source facts. Expose caller-supplied status, timestamp validity, missing evidence categories, freshness, conflicting records, unauthenticated source roles and explicit non-certification language. A caller's `verified` value must be labelled caller-asserted until an authenticated independent verification mechanism exists.

### Growth-fundamentals assessment
Expose category coverage denominator, categories present/missing, source and reporting period, units/currency, stale/invalid evidence, and caller-supplied provenance. The coverage score is evidence coverage only, not a quality score or forecast.

### Cross-source comparison
Expose each observation, metric/unit, time window, comparison tolerances, comparability status, source independence status, conflicts and the reason no preferred source was selected. Do not imply agreement when observations are missing, non-comparable, correlated or outside the comparison window.

## 7. API request and response validation

Future contract tests should cover:
- strict schema version and rejection of unknown fields where the contract is closed;
- required/optional/null field semantics and stable enum vocabularies;
- finite numeric values, integer strictness, numeric bounds, maximum list lengths and text lengths;
- URL/reference field constraints and safe display behavior;
- timezone-aware timestamps and impossible temporal ordering;
- pagination, response-size bounds and stable ordering;
- explicit error schema without internal stack traces, secrets or provider response bodies;
- backward-compatible additive evolution and explicit breaking-version behavior;
- all module response envelopes against shared JSON Schema/OpenAPI contract fixtures;
- read-only semantics and absence of unapproved persistence or side effects.

Response tests must verify not just that fields exist, but that they do not overstate evidence. In particular: caller-supplied `verified` is not CIN verification; a hostname count is not independent corroboration; a fingerprint is not authenticity; complete coverage is not truth; and a numeric score is not a probability.

## 8. Consumer and dashboard safety requirements

- Use explicit labels such as "caller supplied", "provider retrieved", "fallback source", "stale", "partial", "unknown", "conflicting", and "not assessed".
- Display the assessment clock and source observation time separately.
- Show methodology ID/version and a concise explanation of material score components and exclusions.
- Place limitations and warnings adjacent to the result they qualify; do not hide them in a generic footer.
- Never use green success styling for an unverified or incomplete result. Use neutral/amber warning states as appropriate.
- Do not show a single confidence gauge unless its statistical meaning and calibration have been independently validated.
- Provide drill-down to provenance and missing evidence, while avoiding unrestricted external URL fetching.
- Distinguish "no evidence supplied" from "evidence reviewed and not found".
- Keep read-only status visible; do not show trade/order controls in assessment interfaces.
- Accessibility: status must be conveyed in text and not by color alone; support keyboard and small-screen layouts.

## 9. Error and failure contract

Use a stable machine-readable error shape with a non-sensitive code, safe message, retryability classification, correlation/request ID where approved, and optional field-level validation details. Do not return stack traces, secrets, internal file paths, raw provider bodies, or user-submitted free text in generic server errors.

Distinguish invalid request, unsupported contract version, rate limit, provider unavailable, partial provider result, stale cache, internal processing failure and authorization failure. A provider outage must not be represented as an empty successful assessment. Retryability must reflect the actual failure class and avoid uncontrolled retry amplification.

## 10. Current gaps and staged implementation

Current module APIs have meaningful per-module request validation and safety flags, but no shared response-envelope contract or cross-module conformance suite is evidenced in this review. Current response fields vary and some modules use distinct terminology. Methodology identity, input snapshot ID and a single explicit assessment clock are not consistently required across all outputs. Some timestamps are supplied by callers; provider retrieval/fallback provenance exists in coin screening but is not a uniform envelope.

Proposed implementation sequence:
1. Approve a common vocabulary and response schema version.
2. Define stable entity identity and time-field semantics.
3. Add shared response models and module adapters without changing assessment formulas.
4. Add JSON Schema/OpenAPI contract fixtures and conformance tests for all modules.
5. Add consumer-safe labels and dashboard presentation rules.
6. Bind methodology and reproducibility metadata as F-16/F-18 capabilities become available.
7. Add compatibility tests and a deprecation policy before any public breaking change.
8. Perform an independent consumer-safety review before production reliance.

Acceptance requires all four modules to emit contract-conformant envelopes, all unknown/missing values to retain explicit semantics, all source modes and time fields to be traceable, and tests to reject misleading verification/confidence claims.

## 11. Unresolved decisions

- Final shared enum vocabulary and contract versioning policy.
- Stable CIN entity ID strategy and chain/contract identity rules.
- Whether any public consumer needs pagination or long-lived assessment IDs.
- Source-reference disclosure and URL retention constraints.
- Statistical basis for any uncertainty/confidence level.
- Compatibility/deprecation period for API consumers.
- Dashboard design details and accessibility acceptance owner.

## 12. Explicit non-actions

No runtime code, response model, API route, schema, formula, score, threshold, provider, data source, persistence wiring, authentication, deployment, Render setting or Cloudflare setting was changed. No caller-supplied status was promoted to verified. No trading, order execution, wallet control or fund movement is in scope.

**Acceptance status:** F-19 contract and consumer-safety readiness documented; shared schema, conformance tests and dashboard enforcement remain unimplemented. Step 23 remains Partial.
