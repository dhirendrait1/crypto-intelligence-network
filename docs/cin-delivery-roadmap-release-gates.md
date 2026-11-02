# CIN delivery roadmap and release gates

Status baseline: 2026-11-02. This document is an **evidence-aware delivery tracker**, not a claim that every earlier numbered audit step has shipped.

## Non-negotiable scope

CIN is public/read-only cryptocurrency intelligence: market data, analytics, screening, research, monitoring and alerts. No order placement, routing, execution, trading-account access, wallet control, funds movement or private keys. Keep development $0-first; do not activate paid resources or deploy production changes without explicit owner coordination.

## Roadmap workstreams and acceptance criteria

| Workstream | Acceptance gate | Evidence needed before COMPLETE |
| --- | --- | --- |
| Architecture and boundaries | Read-only interface and explicit exclusions across modules | Published module contracts, API review and regression tests |
| CI and repository foundation | Reproducible install and automated tests | Green checks for the **exact** merge candidate commit |
| Market data and provider reliability | Well-defined provider identity, time, volume, precision and failure handling | Offline provider fixtures, edge-case regressions and no synthetic provider candles |
| Technical analysis | Deterministic indicators on validated closed candles | Golden fixtures, parameter validation and timestamp freshness tests |
| Coin screening and fundamentals | Explicit candidate eligibility before ranking | Unit-tested filters for liquidity, tokenomics, data reliability and missing fields |
| On-chain and whale intelligence | Traceable observations, not unverifiable attribution | Provenance, chain-specific interpretation, confidence and coverage tests |
| Derivatives and liquidation research | Read-only, provider-qualified observations | Source/market identity, timing, units and failure tests |
| News and sentiment | De-duplicated verified sources and confidence indicators | News provenance, publication-time handling and fallback tests |
| Evidence fusion and ranking | Separable eligibility gates, weighted score and confidence | Deterministic fixtures, missing-data behavior and score-version tracking |
| Risk/scenario analysis | Explicit assumptions, downside and invalidation | Scenario validation, sensitivity checks and no guaranteed-return claims |
| Monitoring and alerting | Idempotent, bounded, auditable delivery | Retry/crash/restart tests, delivery deduplication and opt-in routing |
| Dashboard and mobile UX | Accurate data-driven read-only views | API contract tests, usable Android layout and clear freshness/error states |
| Release and operations | Full end-to-end quality gate | Reviewed merge chain, security checks, staging smoke tests and documented rollback |

## PR reconciliation gate (required before claiming completion)

1. Inventory every open PR and identify its head/base SHAs; note draft state, stale branches and overlapping changes.
2. For each stacked PR, record its parent dependency. Never count PR numbers or step numbers as completed deliverables.
3. Check exact-head workflow runs and required status checks. A PR description saying tests were added is **not** proof that tests passed.
4. Audit duplicate or superseded tests and code across stacked branches; preserve distinct coverage.
5. Validate proposed merge order and regression suite after each integration step.
6. Keep unreviewed changes in draft branches. Do not merge, deploy to Render, activate Cloudflare routes or change production settings automatically.

## Current verified observations (as of baseline)

- The main branch contains prior public market-candle and technical-analysis work, provider fallback, and public-news research commits.
- The open draft audit chain includes Coinbase response and product-metadata validation through PR #199, stacked on PR #198.
- PR #199 describes offline tests and its exact-head CI/local execution as *not yet verified*.
- This document does not assert production availability, CI success or feature completion without matching artifacts.

## Immediate delivery sequence

**Gate A — Reconcile:** obtain base/head and exact-head CI for PR #199 and its dependency chain; identify earliest unmerged ancestor and blocking checks.

**Gate B — Integrate:** safely consolidate distinct provider-reliability tests into a small reviewable merge sequence, with all existing public API contracts protected.

**Gate C — Shortlist engine:** implement deterministic eligibility filters and a versioned transparent ranking specification; treat missing critical evidence as insufficient-data, not a neutral score. Start with read-only fixtures and no paid providers.

**Gate D — Dashboard:** expose shortlist status, supporting evidence, confidence, freshness, data gaps and risk overrides in Android-friendly views; use disabled-by-default gates until end-to-end tests pass.

**Gate E — Release:** require complete CI and security results, staging checks, owner review of any account-level actions, and a documented rollback path.

## Reporting format for every subsequent work session

Report (a) commit/PR links, (b) exact tests that ran and results, (c) what is merged vs only proposed, (d) remaining blockers, and (e) the next **distinct** work item. Do not create another audit step merely to advance numbering.
