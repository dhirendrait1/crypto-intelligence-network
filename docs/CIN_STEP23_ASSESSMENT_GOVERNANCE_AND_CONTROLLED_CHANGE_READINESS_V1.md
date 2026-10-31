# CIN Step 23 — Assessment Governance, Methodology Approval and Controlled Change Readiness (F-18)

**Status:** Governance/readiness design only  
**Date:** 2026-10-31  
**Scope:** Coin screening, commodity-backing assessment, growth-fundamentals assessment, cross-source evidence comparison, and shared evidence/claim assessment primitives.

## 1. Purpose and boundaries

F-18 defines internal technical governance for controlled changes to assessment methodology and the handling of historical assessment results. Its purpose is to prevent undocumented formula drift, ambiguous approval, unauthorized promotion of review states, and loss of historical context.

This is an internal engineering and research-quality control. It does not create a government approval, licence, certification, regulator, external accreditation, or legal-compliance process. It does not establish investment merit, certify issuers or reserves, or authorize trading.

F-18 is design-only. No runtime behavior, formula, score, threshold, provider, schema, API, persistence, or deployment is changed.

## 2. Governance principles

1. **Explicit ownership:** every methodology has a named technical owner and a separately identified reviewer for material changes.
2. **Versioned semantics:** any change that can alter interpretation or output receives a new methodology version.
3. **Evidence-backed approval:** decisions cite the exact diff, test results, benchmark results, known limitations, and affected scope.
4. **Separation of duties:** authors cannot self-approve material methodology changes.
5. **No silent historical rewrite:** previously issued assessment records remain attributable to the version and inputs used at the time.
6. **Fail closed:** missing approval, missing required evidence, unresolved critical defects, or ambiguous version identity blocks release.
7. **Reversible release:** retain the last approved version and a reviewed rollback/hold path.
8. **Proportional governance:** documentation-only, non-semantic changes do not require the same review burden as changes to scoring, source authority, eligibility, or verification semantics.
9. **Transparent uncertainty:** unknown, stale, partial, conflicting, and not-assessed states remain distinct.
10. **No unsupported claims:** approval means internal process acceptance, not truth certification or guaranteed predictive performance.

## 3. Roles and responsibilities

| Role | Responsibility | Restrictions |
|---|---|---|
| Methodology owner | Maintains purpose, definitions, inputs, assumptions, version and limitations | Cannot solely approve own material change |
| Implementation owner | Maintains code, tests, interfaces and reproducibility metadata | Must disclose implementation deviations |
| Independent technical reviewer | Reviews semantics, evidence, test results and risk | Must not be the sole author of the change |
| Data/source steward | Reviews source permission, provenance, quality, coverage and comparability | Cannot declare a source independently verified without evidence |
| Release maintainer | Confirms gates, records release identity and can hold/rollback | Cannot waive a critical gate without an approved exception authority |
| Assessment consumer | Reports defects and interprets outputs within stated scope | Cannot modify methodology or promote review status by assertion |

One person may hold multiple non-conflicting operational roles in a small project, but the author and independent reviewer for a material change must be distinct. Role names in a record are not proof of authenticated identity. Authentication and authorization remain separate prerequisites before privileged workflows are implemented.

## 4. Methodology registry contract

A future registry should maintain immutable, versioned records with at least:

- stable methodology ID and semantic version;
- human-readable name, purpose, supported module and intended use;
- input metric definitions, units, source classes and eligibility rules;
- formulas, component weights, thresholds, exclusions and missing-data behavior;
- freshness and assessment-clock rules;
- source precedence and fallback comparability rules;
- uncertainty, abstention, conflict and limitation semantics;
- effective-from timestamp and superseded-by relationship;
- code commit, schema/API version and runtime/dependency fingerprint;
- linked reproducibility envelope, test catalogue and benchmark/reference-set versions;
- author, independent reviewer, decision record and approval timestamps;
- status: draft, in_review, approved, active, deprecated, suspended, or rejected;
- change rationale, compatibility notes and known defects.

A registry entry must not be mutable in place after approval. Corrections and semantic changes create a new version linked to the prior version. The registry itself requires access control, audit history, backup and retention policy before production use.

## 5. Semantic versioning policy

Use a documented semantic scheme, such as MAJOR.MINOR.PATCH, with these meanings:

- **MAJOR:** changes intended use, output interpretation, eligibility semantics, core metric definitions, source authority, or compatibility in a way that can materially change conclusions.
- **MINOR:** adds a documented metric, optional component, source mapping, or capability while preserving prior interpretation for existing inputs.
- **PATCH:** fixes an implementation defect without intentionally changing methodology semantics. If outputs change for previously valid inputs, disclose the affected scope and evaluate whether a MINOR or MAJOR increment is more honest.

Version numbers alone do not prove compatibility. Every release must include a machine-readable or otherwise stable methodology manifest and a human-readable change note. Never reuse a version identifier for different semantics.

## 6. Change classification and required review

| Change class | Examples | Minimum review |
|---|---|---|
| Editorial/non-semantic | Typo, formatting, clarification that does not change interpretation | Owner review and documentation check |
| Implementation-preserving | Refactor with demonstrated identical outputs on frozen fixtures | Unit/regression tests, differential comparison, reviewer |
| Data/source | Provider addition/removal, fallback change, source priority, field mapping | Source permission/provenance review, coverage and comparability tests, independent reviewer |
| Methodology-semantic | Formula, weight, threshold, eligibility, unit, freshness, or missing-data rule change | New version, F-16 reproducibility, F-17 benchmark/error review, independent approval |
| Safety/verification semantics | Changing what counts as verified, corroborated, backed, or conflict-resolved | New version, evidence-policy review, independent approval, explicit limitations |
| Emergency correction | Critical defect or misleading output requiring rapid hold/fix | Immediate affected-scope hold, incident record, expedited independent review, retrospective documentation |

A change must be classified by its greatest plausible impact, not by the author's preferred label. A patch that changes an output for valid inputs is not automatically non-semantic.

## 7. Approval workflow

The proposed controlled workflow is:

1. **Proposal:** record change ID, motivation, affected modules/assets/periods, risk, intended behavior, and rollback plan.
2. **Baseline capture:** pin current code, methodology, schema, runtime, input fixtures, source provenance and baseline outputs.
3. **Impact analysis:** identify changes to inputs, units, formulas, thresholds, eligibility, source dependencies, uncertainty and API contracts.
4. **Implementation and evidence:** attach code diff, tests, reproducibility evidence, benchmark/error analysis and coverage changes.
5. **Independent review:** reviewer records approve, request_changes, reject, or abstain with rationale and conflict disclosure.
6. **Disposition:** resolve every blocking finding; unresolved critical/high findings prevent approval.
7. **Release authorization:** release maintainer verifies all applicable gates and records exact artifact identities.
8. **Post-release observation:** monitor defined indicators, compare expected/actual distributions and document incidents.
9. **Retirement or rollback:** suspend/deprecate affected version through a new record; preserve historical lineage.

Approval records must be append-only once persisted. A later reversal is a new decision event, not an edit that erases the prior approval.

## 8. Approval evidence and exception policy

A material approval record should include:
- change and methodology IDs/versions;
- exact source commit and build/artifact identity;
- baseline and candidate reproducibility fingerprints;
- test-run identifiers and outcomes;
- reference dataset/benchmark version and evaluation period;
- per-module/per-stratum FP/FN, coverage, abstention and uncertainty results where applicable;
- source permissions and provenance review outcome;
- reviewer identity evidence, role, independence declaration and timestamp;
- findings, remediation links, residual risk and explicit decision;
- release/hold decision and rollback reference.

Exceptions must be narrow, time-bounded, owned, justified and recorded with compensating controls. A critical safety, integrity, provenance, or data-leakage defect cannot be waived for convenience. Do not invent a numeric exception duration or performance threshold before the relevant owner and risk basis are approved. Expired exceptions automatically return to hold/review in any future implementation.

## 9. Historical assessment immutability and re-evaluation

- Each assessment result must identify the exact methodology version, code/runtime identity, schema version, assessment clock, inputs/snapshot reference and provenance.
- A new methodology version does not rewrite prior outputs.
- Re-evaluation creates a new assessment record linked to the prior assessment with a reason such as methodology update, corrected source data, defect remediation, or user-requested replay.
- Preserve the distinction between "what CIN concluded at the time" and "what CIN concludes under the current methodology."
- If a defect invalidates prior results, mark them as affected, under review, or superseded using a new append-only event. Do not erase or silently replace the original record.
- Historical replay must state whether original inputs are exactly available, partially reconstructed, or unavailable. A replay from changed or incomplete data is not exact reproduction.
- Retention and erasure obligations remain governed by the separate F-02/F-05 design gates; immutability must not be used to bypass an approved lawful erasure process.

## 10. Module-specific governance controls

### Coin screening
Changes to component weights, score bands, asset-type classification, eligibility, freshness holds, provider precedence or fallback mapping are semantic when they can alter candidate status or score interpretation. Preserve prior weight sets and compare baseline/candidate outputs on the same frozen universe.

### Commodity-backing assessment
Changes to what qualifies as issuer evidence, custody evidence, reserve evidence, independent attestation, redemption rights, or verified backing are high-impact semantic changes. Caller-supplied evidence must not be promoted to verified solely through a methodology update.

### Growth-fundamentals assessment
Changes to financial metric definitions, reporting-period alignment, accounting basis, estimate handling, source authority, or growth thresholds require versioning and point-in-time benchmark review. Historical revisions must not leak into earlier assessment dates.

### Cross-source evidence comparison
Changes to entity matching, source independence, metric comparability, units, tolerances, observation windows, or conflict semantics require a new version and targeted adversarial tests. Multiple copied sources must not become independent corroboration through a policy change.

## 11. Suspension, rollback and incident handling

Suspend a methodology version or affected module when there is evidence of:
- materially incorrect or misleading output;
- source/entity misattribution or unsupported verification;
- corrupted or irreproducible inputs;
- temporal leakage or benchmark contamination;
- an unapproved semantic change;
- a critical unresolved security, privacy, retention or integrity defect.

The hold record should identify affected versions, outputs/time window, known scope, consumer warning, containment action, owner and next review. Rollback restores a previously approved version only after compatibility and data-lineage checks. It does not delete assessments produced by the suspended version.

## 12. Current repository evidence and gaps

The repository contains:
- documented coin-screening weights and module-specific behavior;
- shared evidence/claim primitives with constrained vocabularies;
- append-only assessment-event support in the local SQLite reference adapter;
- F-16 reproducibility and F-17 QA/validation readiness designs.

The reviewed repository does not evidence:
- a shared immutable methodology registry;
- enforced author/reviewer separation or authenticated reviewer identities;
- an approval workflow or role-based release authorization;
- semantic version enforcement across assessment outputs;
- append-only approval/exception/suspension decision events in a production store;
- automatic historical impact analysis, replay or rollback orchestration.

The local SQLite adapter is development/test-only and is not connected to the public API. Vocabulary validation and append-only event insertion do not themselves implement the governance workflow described here.

## 13. Implementation sequence and acceptance criteria

Future implementation should be separately authorized and staged:

1. Define methodology manifest schema and version compatibility rules.
2. Define approval/decision event schema and authenticated role/permission model.
3. Add immutable registry/repository contracts and local deterministic tests.
4. Bind every assessment result to methodology and reproducibility identity.
5. Add change-impact and baseline/candidate comparison tooling.
6. Add approval gates to release workflow only after roles and authority are configured.
7. Add suspension/deprecation/rollback records and historical impact visibility.
8. Conduct an independent end-to-end review before any production reliance.

Acceptance requires tests for duplicate version rejection, immutable approved manifests, semantic version enforcement, author/reviewer separation, unauthorized approval denial, incomplete evidence hold, exception expiry, approval reversal as a new event, historical result preservation, replay linkage, suspension propagation and rollback lineage.

## 14. Unresolved decisions

The following remain intentionally undecided:
- named role holders and how identity is authenticated;
- who has final internal release authority;
- semantic-version compatibility policy for external consumers;
- benchmark acceptance thresholds and minimum sample sizes (F-17);
- exception authority and maximum duration;
- approval-event retention and privacy rules;
- production registry storage and access controls.

These are internal project decisions, not government licensing or approval requirements.

## 15. Explicit non-actions

No runtime code, methodology formula, score, threshold, provider, source precedence, schema, API, persistence wiring, authentication, authorization, approval workflow, deployment, Render service, or Cloudflare configuration was changed. No assessment was approved, promoted, certified, or re-evaluated. No trade execution, wallet control, or fund movement is in scope.

**Acceptance status:** F-18 governance and controlled-change design documented; registry, approval workflow, enforcement and historical governance automation remain unimplemented. Step 23 remains Partial.
