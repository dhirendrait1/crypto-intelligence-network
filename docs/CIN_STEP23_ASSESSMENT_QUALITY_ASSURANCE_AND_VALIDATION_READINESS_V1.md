# CIN Step 23 — Assessment Quality Assurance and Validation Readiness (F-17)

**Status:** Design/readiness assessment only  
**Date:** 2026-10-31  
**Scope:** Coin screening, commodity-backing assessment, growth-fundamentals assessment, and cross-source evidence comparison.

## 1. Purpose and decision boundary

This document defines the validation controls required before CIN assessment outputs can be treated as dependable research evidence. It does not certify an asset, issuer, reserve claim, source, methodology, or investment outcome. A heuristic score is not a probability, recommendation, or guarantee.

F-17 is a readiness design. It does not change runtime code, scoring formulas, thresholds, providers, data collection, persistence, deployment, or trading behavior.

## 2. Current repository evidence and gaps

The repository already contains offline unit/regression coverage, including:
- `tests/test_coin_screening.py`: finite-number handling, stale/unknown freshness holds, asset classification, provider fallback mapping, cache behavior, score bounds, and growth-candidate exclusions.
- `tests/test_commodity_backing_assessment.py` and API tests: assessment and request/response validation coverage.
- `tests/test_growth_fundamentals.py`, validation and API tests: growth assessment behavior and input validation.
- `tests/test_cross_source_evidence.py` and API tests: cross-source comparison behavior and API contracts.
- GitHub Actions runs on the active PR branch provide offline CI evidence.

These tests are useful but do not constitute a unified quality system. The reviewed repository has no evidenced, centrally governed benchmark/ground-truth registry, independent validation protocol, cross-module traceability matrix, shared false-positive/false-negative reporting, calibrated confidence framework, or release-quality dashboard. Existing tests must not be represented as independent validation.

## 3. Validation taxonomy

Each test must be labelled by purpose; passing one class does not substitute for another.

| Class | Required role | Minimum evidence |
|---|---|---|
| Unit | Validate deterministic functions and edge cases | Test ID, fixture, expected result |
| Contract | Validate API/schema and provider mapping boundaries | Versioned schema and positive/negative cases |
| Integration | Validate module interactions using controlled fixtures | Dependency graph and captured outputs |
| Regression | Prevent previously observed defects from returning | Linked defect, fixed fixture, expected invariant |
| Property/fuzz | Exercise broad input classes and invariants | Seed, generator/version, bounds, minimized failures |
| Differential | Compare independent implementations or reference calculations | Reference implementation, tolerances, disagreements |
| Independent validation | Assess methodology and labels outside the implementation authoring path | Reviewer independence, protocol, findings, disposition |
| Operational monitoring | Detect live drift, freshness, provider failures and distribution changes | Minimized telemetry, alert owner, runbook |

Test suites should follow a practical test pyramid: many fast offline unit/property tests, fewer contract and integration tests, and controlled benchmark/independent review gates. Live provider tests are not a substitute for deterministic offline tests and must never make ordinary CI depend on third-party availability.

## 4. Traceability and evidence record

Every material requirement must map to:
1. a requirement/control ID;
2. one or more test-case IDs;
3. the fixture or reference dataset version;
4. expected invariant or adjudicated label;
5. actual result and test-run identifier;
6. code commit, schema/API version, and methodology version;
7. reviewer, review date, and unresolved exception where applicable.

A test without a stable fixture/version and expected assertion is not reproducible evidence. A passing workflow is evidence that its configured jobs passed; it is not evidence that the methodology is valid or that all relevant failure modes were tested.

## 5. Ground truth, labels, and independent reference sets

- Build reference sets from sources with documented provenance, permitted use, observation time, entity identity, metric definition, and known limitations.
- Separate source facts, adjudicated labels, and model/module outputs. Never use the module's own output as its ground truth.
- For disputed or ambiguous cases, use an explicit `unknown`, `unresolved`, or `not_assessed` label rather than forcing a binary positive/negative label.
- Record label rationale, evidence links/IDs, adjudication protocol, reviewer role, and disagreement resolution.
- Independent validation must not be performed solely by the author of the assessed formula or implementation. Reviewer identity/authenticity and conflict-of-interest controls must be established before relying on a `human_reviewed` flag; a caller-supplied flag is not authenticated review.
- Keep train/tune/reference and final evaluation sets separated. Freeze evaluation labels before scoring changes are assessed. Avoid using future information in historical labels.
- Respect source licences, terms, privacy, and retention rules. Use minimized synthetic or appropriately licensed fixtures where possible; do not place credentials, private user data, or restricted source payloads in tests.

## 6. Error measurement and uncertainty

Where a module produces a binary classification and defensible reference labels exist, report the confusion matrix (TP, FP, TN, FN), precision, recall/sensitivity, specificity, and F1 where appropriate. State the positive class, denominator, evaluation period, asset universe, label policy, and treatment of unknowns.

- False positives and false negatives must be reviewed separately; aggregate accuracy alone can conceal severe class imbalance.
- Report sample counts and uncertainty intervals for rates. Small or biased samples must be labelled inconclusive.
- Stratify results by asset type, liquidity/coverage tier, source availability, chain/venue, time period, and relevant market regime where sample sizes permit.
- Do not invent universal pass thresholds. Thresholds require a documented risk rationale, representative reference set, minimum sample size, and explicit approval.
- If the system abstains because data is stale, missing, conflicting, or out of scope, measure abstention/coverage separately. Do not silently count abstentions as correct predictions or convert unknown to negative.
- A numerical heuristic score must not be described as a probability. Calibration (for example, reliability curves or Brier score) is applicable only if CIN later defines a probabilistic target, obtains representative labelled outcomes, and validates calibration out of sample.

## 7. Temporal and universe controls

For time-dependent market or fundamentals analysis:
- Use time-based splits and walk-forward evaluation where forecasting or historical decision quality is being assessed.
- Enforce point-in-time availability: inputs must have been observable at the simulated assessment time. Prevent look-ahead leakage from later revisions, later disclosures, or future price/volume data.
- Avoid survivorship bias by retaining delisted, failed, migrated, renamed, and illiquid assets in historical evaluation where lawful and data is available.
- Version the eligible asset universe and record inclusion/exclusion reasons, venue/chain scope, quote currency, and coverage gaps.
- Evaluate across materially different market regimes rather than selecting only a favorable period.
- Keep cross-sectional ranking tests distinct from forecasting tests; a ranking score does not prove predictive performance.

## 8. Mandatory edge-case families

The shared test catalogue should include, as applicable:

- Missing, null, zero, negative, non-finite, oversized, malformed, and type-confused numeric values.
- Stale, future-dated, timezone-naive, invalid, duplicated, and out-of-order timestamps.
- Partial pages, cursor exhaustion, provider truncation, duplicate entities, missing fields, and unobserved universe segments.
- Primary-provider failure, fallback-provider mismatch, stale-cache fallback, source disagreement, and provider schema drift.
- Quote-currency mismatch, unit/scale mismatch, token redenomination, wrapped/staked assets, stablecoins, commodity-backed tokens, and ambiguous symbol collisions.
- Extreme volatility, illiquidity, zero-volume intervals, market closures, thinly traded assets, and abrupt supply/FDV changes.
- Conflicting evidence, unsupported claims, unverifiable issuers, expired attestations, and missing provenance.
- Boundary values around every documented threshold, including exact equality and rounding behavior.
- Repeated execution with identical frozen inputs, methodology, and clock; output should be deterministic within the documented runtime envelope.

Every failure must produce a safe, explicit state such as data-quality hold, unknown, partial, or not assessed. Missing evidence is not evidence of absence; a zero value must not be substituted for missing data unless the metric contract explicitly defines that behavior.

## 9. Module-specific validation expectations

### Coin screening
- Verify each component contribution, weight, bounds, missing-metric behavior, exclusions, deduplication, freshness hold, and provider fallback provenance.
- Test that high raw metric scores cannot override excluded asset categories or data-quality holds.
- Treat screening bands as heuristic research filters, not forecasts or recommendations.
- The existing documented weight set must be versioned before any future formula change; do not silently alter weights under the same methodology version.

### Commodity-backing assessment
- Separate evidence of token/issuer identity, legal claim, custody, reserve quantity, valuation, audit/attestation, redemption rights, and independent verification.
- Test that issuer statements or caller-supplied evidence are not promoted to independently verified facts.
- Missing, stale, unauthenticated, or conflicting reserve evidence must remain explicit; do not infer backing from token price, ticker, or marketing language.
- Define asset-specific units, valuation timestamps, liability denominator, and reconciliation tolerances before any quantitative coverage ratio is interpreted.

### Growth-fundamentals assessment
- Validate metric definitions, reporting periods, currencies, accounting basis, source quality, revision history, and comparability.
- Test negative/zero denominators, missing periods, inconsistent fiscal calendars, one-off events, extreme growth rates, and stale disclosures.
- Distinguish observed historical fundamentals from forecasts and analyst estimates; retain source and period for every input.
- A favorable score must not imply future returns or investment suitability.

### Cross-source evidence comparison
- Test entity resolution, metric comparability, units, observation windows, source independence, freshness, and tolerance boundaries.
- Correlated or copied sources must not be counted as independent corroboration.
- A disagreement is a conflict signal requiring interpretation, not automatic proof that one source is false.
- Missing source observations must not be represented as agreement.

## 10. Reproducibility and change control

F-16's reproducibility envelope is a prerequisite for reliable regression and benchmark comparisons. Freeze and retain the exact input snapshot or permitted immutable reference, source/cache/fallback provenance, assessment clock, parameters, methodology version, code commit, schema/API version, runtime/dependency fingerprint, and output fingerprint.

For every methodology or scoring change:
1. document the intended behavior change and rationale;
2. increment the methodology version when semantics change;
3. run the unchanged baseline and candidate against the same frozen evaluation set;
4. report per-module and per-stratum changes, including regressions and abstention/coverage changes;
5. obtain independent review for material changes;
6. retain prior results and replay evidence without overwriting historical assessments.

## 11. Release gates and severity

Proposed gates are controls to be approved, not currently configured CI thresholds.

- **Gate A — Data integrity:** schema/contract tests pass; invalid, stale, incomplete, and conflicting inputs fail safely.
- **Gate B — Determinism:** frozen-input regression and replay tests pass under the declared environment.
- **Gate C — Benchmark validity:** reference set is representative, independently governed, sufficiently sized, and free of known temporal leakage.
- **Gate D — Performance and error review:** FP/FN and coverage results are reported by relevant strata; no unexplained material regression is accepted.
- **Gate E — Independent review:** material methodology changes receive documented independent assessment and disposition.
- **Gate F — Operational readiness:** monitoring, ownership, source-failure handling, rollback/hold procedure, and data-retention controls are approved before production reliance.

Severity handling:
- **Critical:** leakage, fabricated/unsupported verification, silent corruption, or a result that reverses a material decision. Block release and quarantine affected outputs.
- **High:** material FP/FN regression, source/entity misattribution, or unsafe handling of stale/conflicting evidence. Block affected module release.
- **Medium:** bounded edge-case or comparability defect with a safe hold state. Track with owner and due date; release only with explicit exception.
- **Low:** presentation/documentation defect with no change to underlying result semantics. Record and schedule normally.

No numeric performance threshold is asserted here. Release thresholds, minimum sample sizes, risk appetite, and exception authority remain unresolved governance decisions.

## 12. Rollback, hold, and post-release controls

- A failed gate holds the affected module/methodology version; it does not justify silently changing outputs or rewriting historical records.
- Preserve the last approved version and its reproducibility envelope. Roll back only through a reviewed, versioned release action.
- Mark affected outputs as under review or superseded where a material defect is confirmed; preserve audit lineage.
- Monitor source freshness, coverage, fallback frequency, schema drift, output distributions, abstention rates, and delayed reference-label outcomes where permitted.
- Define alert owners, response windows, evidence retention, incident classification, and communication before relying on production monitoring.

## 13. Current status and unresolved decisions

**Present:** offline unit/regression tests across the four assessment areas and successful configured GitHub Actions CI runs.

**Not evidenced as a unified capability:** governed ground-truth/reference datasets, independent validation ownership and protocol, shared confusion-matrix/error reporting, calibrated probabilistic outputs, point-in-time benchmark harness, release thresholds, and production drift monitoring.

**Blocked decisions:** benchmark scope and labels; minimum sample sizes; risk-based error thresholds; independent reviewer authority; methodology-change approval; permitted fixture/source retention; production monitoring owner and response commitments.

## 14. Explicit non-actions

No runtime code, test suite, scoring formula, score threshold, provider, source configuration, schema, persistence behavior, API, Render service, Cloudflare configuration, or deployment was changed by F-17. No live trading, order execution, wallet control, or fund movement is in scope. This document is not a certification or investment recommendation.

**Acceptance status:** F-17 readiness design documented; unified QA/independent validation implementation remains open. Step 23 remains Partial.
