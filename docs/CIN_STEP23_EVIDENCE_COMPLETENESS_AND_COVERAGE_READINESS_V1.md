# CIN Step 23 — Evidence Completeness and Coverage Controls Readiness v1

**Status:** Readiness assessment and implementation contract only. No coverage evaluator, scheduled scan, provider registry, API, or production persistence activated.
**Scope:** Detecting missing sources, missing time windows, partial retrievals, scan gaps, and incomplete claim coverage.
**Boundary:** Research/analysis only; no execution, wallet control, key handling, or fund movement.

## 1. Executive finding

The common verifiable evidence specification already requires assessments to expose expected versus received source/record counts where measurable, missing categories, missing time windows, scan gaps, provider outages, and a complete/partial/stale/unknown result. Evidence records also have fields for limitations, missing fields, and timestamp validation errors.

However, the reviewed implementation does not provide a general coverage plan, expected-source registry, time-window coverage evaluator, pagination/scan completeness proof, gap detector, or assessment-level completeness status. The GitHub connector validates one bounded repository metadata response and reports missing fields/freshness; that is not a general completeness guarantee. The cross-source comparator only compares caller-supplied observations and counts rejected/out-of-window observations; it does not know which sources or time buckets were expected.

**Disposition:** Completeness is specified in the data model, with limited source-specific missing-field/freshness reporting. A reusable coverage evaluator and operational scan accounting remain unimplemented.

## 2. Completeness dimensions

Every assessment should evaluate these dimensions independently; one passing dimension must not hide a gap in another.

| Dimension | Required accounting | Example gap |
|---|---|---|
| Source coverage | Expected, attempted, successful, failed, skipped and disabled sources | One of four approved providers was unavailable |
| Entity coverage | Expected versus resolved canonical entities/instruments | Requested token contract could not be resolved |
| Metric coverage | Required metrics versus received valid metrics | Circulating supply present; holder concentration absent |
| Time coverage | Expected intervals/windows versus valid observations | Missing 02:00–03:00 UTC candles |
| Pagination/scan coverage | Page/cursor ranges, terminal condition, records read, duplicates, truncation | API page cap reached before end |
| Field coverage | Required fields versus present/valid fields | Price returned without quote currency |
| Freshness coverage | Per-record age against metric-specific policy | Latest valid observation exceeds threshold |
| Provenance coverage | Source identity, source time, retrieval time, methodology and lineage | Value has no traceable source URL or observation time |
| Independence coverage | Distinct sources and known shared upstream dependencies | Two feeds reproduce the same upstream publisher |
| Validation coverage | Valid, rejected, malformed, out-of-order and ambiguous records | 15 records rejected for invalid timestamps |

Do not collapse these dimensions into one unexplained percentage. If a summary score is later approved, preserve all component counts and explain weighting and unknown dimensions.

## 3. Assessment coverage manifest

Before a scan starts, define an immutable versioned coverage manifest containing:

- assessment ID, entity/instrument scope, metric set, unit and methodology version;
- requested valid-time start/end, interval/granularity, timezone and boundary convention;
- expected providers/source namespaces and whether each is required or optional;
- expected record cadence/count where the provider contract makes it knowable;
- pagination/scan strategy, maximum pages/records and documented truncation conditions;
- per-metric freshness and timestamp semantics;
- required fields and validation rules;
- fallback eligibility by metric and source;
- manifest creation time, policy version and code/retrieval version.

The manifest is the denominator for coverage accounting. Do not infer the expected source set from whichever providers happened to respond. If expected coverage cannot be established, label the dimension unknown rather than 100%.

## 4. Scan and gap accounting

For each source and metric, record separate counters and status:

- planned, attempted, succeeded, failed, skipped and disabled;
- received, valid, rejected, duplicate and out-of-window records;
- requested pages/cursors, completed pages/cursors, terminal marker observed, page cap reached;
- earliest/latest valid observation and expected window boundaries;
- missing intervals, timestamp gaps, overlapping intervals and late-arriving records;
- required fields missing and source schema/version changes;
- provider error class (429, timeout, 5xx, DNS/TLS, malformed response, size cap).

A scan is not complete merely because HTTP returned 200 or the loop ended. It is complete only when the source's documented terminal condition is reached and all required validation/accounting gates pass. If the provider does not expose a reliable terminal marker or total count, record completeness as unknown or bounded-partial.

For time-series data, compare expected buckets to received valid buckets using explicit interval and timezone rules. Do not assume a missing candle/value is zero; do not silently forward-fill or interpolate. Any future interpolation must be separately labeled as derived and disclose the gap.

## 5. Assessment-level status rules

Use explicit states, with precedence that prevents a green summary from masking failure:

- **complete:** all required sources, entities, metrics, fields and time windows were accounted for; source terminal conditions and validation gates passed; no unresolved required gaps remain.
- **partial:** some required data was retrieved, but one or more required sources, fields, pages, metrics or windows are missing or truncated.
- **stale:** relevant data exists but violates its metric-specific freshness policy; retain partial/unavailable flags where applicable.
- **unavailable:** required data could not be obtained or validated for the requested scope.
- **unknown:** expected coverage or source completion cannot be determined from available contracts/evidence.
- **not_assessed:** no coverage evaluation was performed.

Keep retrieval success, schema validity, freshness, completeness, and claim verification as separate fields. A successful retrieval can still be partial, stale, incomparable, or unverified. A coverage-complete scan does not prove that the underlying claim is true.

## 6. Safe interpretation and UI/API requirements

- Show requested scope and actual covered scope side by side.
- Show source status and last successful retrieval per provider.
- Show missing time ranges and metrics, not just a generic warning.
- Distinguish zero observed records from missing/unavailable records.
- Expose page/record caps and truncation.
- Keep fallback observations labeled with their own source and provenance.
- Do not calculate confidence or investment scores from coverage percentage alone.
- Do not describe an assessment as comprehensive if any required dimension is partial or unknown.
- Preserve the coverage manifest and scan summary with the assessment snapshot when persistence is approved.

## 7. Acceptance tests before implementation

Require deterministic fixtures for:

1. All expected sources return complete valid coverage.
2. One required source fails while optional sources succeed.
3. One required provider is disabled or skipped.
4. A page cap is reached before the provider terminal marker.
5. A cursor repeats, skips, or terminates unexpectedly.
6. A time-series bucket is missing, duplicated, overlapping, delayed, or out of order.
7. A required metric or field is absent despite HTTP 200.
8. Returned data includes malformed, stale, future, timezone-naive, or invalid observations.
9. Duplicate records and syndicated upstream sources do not inflate coverage or independence.
10. A source cannot expose total count/terminal state and coverage becomes unknown, not complete.
11. Provider fallback occurs with explicit source identity and preserved primary failure.
12. No missing value is converted to zero or silently interpolated.
13. Manifest version changes produce a distinct assessment basis.
14. API errors, process restarts, or partial writes cannot emit false complete status.
15. Summary counts reconcile exactly to per-source/per-metric/per-window detail.

## 8. Current gaps and dependencies

| Gap | Current disposition |
|---|---|
| Common evidence model completeness fields | Specified, not generally enforced |
| GitHub connector missing fields and freshness | Source-specific reporting exists |
| Cross-source comparator | Caller-supplied only; not an expected-coverage engine |
| Versioned expected-source/metric manifest | Not evidenced |
| Time-window and pagination terminal accounting | Not evidenced as reusable control |
| Coverage status evaluator | Not implemented |
| Provider-specific freshness/requiredness registry | Depends on provider governance |
| Persisted coverage snapshots | Depends on reviewed persistence integration and policy |
| UI/API gap visualization | Not implemented by this review |
| Live provider completeness validation | Not performed |

## 9. Explicit non-actions

No provider was added or queried. No source was promoted, no data was backfilled, and no cache, scheduler, pagination client, coverage percentage, confidence score, API endpoint, database schema, persistence wiring, deployment, Render/Cloudflare setting, or paid service was created or changed.

**Disposition:** Completeness dimensions, scan accounting, status semantics, and acceptance tests are documented. Runtime coverage evaluation and live validation remain open. Step 23 remains Partial.
