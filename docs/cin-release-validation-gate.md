# CIN Release Validation Gate

**Status:** Not release-approved  
**Last reconciled:** 2026-10-27  
**Scope:** Read-only market-data ingestion, candle provenance, and analysis metadata.

## Current stacked changes

- PR #49 — market-candle provenance helpers. Open, draft, unmerged. Its description reports CI success, but live provider and deployed-service behavior are not proven by those checks.
- PR #50 — provenance contract integration tests. Open, draft, unmerged. Automated validation is not confirmed.
- PR #51 — Kraken returned-market identity validation. Open, draft, unmerged. Regression tests are committed; execution on the latest head is not confirmed.

All three are dependent work. Review the shared base and combined behavior before merging; do not merge a dependent PR independently of its base.

## Required release gates

### 1. Automated tests
- [ ] Confirm the intended GitHub Actions workflows trigger for the latest PR head commits.
- [ ] Record the run URLs, tested commit SHAs, and final conclusions.
- [ ] Run the focused market-candle and provenance tests.
- [ ] Run the full repository CI matrix required by the project.
- [ ] Confirm mismatch, ambiguous-key, missing-market-key, quote-mapping, timestamp-semantics, and conservative provenance-flag regressions are covered.

An empty status response or missing workflow-run result is **unverified**, not a pass or a failure.

### 2. Provider contract
- [ ] Check Kraken's returned result key against the requested base/quote pair and documented aliases.
- [ ] Verify unexpected or ambiguous keys fail closed.
- [ ] Check edge cases for non-USD quotes and assets beyond BTC/ETH before claiming broad pair coverage.
- [ ] Keep provider observation timestamps distinct from retrieval timestamps and candle open/close semantics.

### 3. Provenance semantics
- [ ] Preserve requested quote versus actual quote as separate fields.
- [ ] Do not claim freshness unless a defined freshness policy has actually been applied.
- [ ] Do not claim source authenticity is verified merely because metadata is structurally valid.
- [ ] Treat unknown, incomplete, or inconsistent metadata conservatively.

### 4. Deployed-service validation
- [ ] Only after GitHub checks pass, arrange a separately authorized read-only smoke test against the deployed API.
- [ ] Record endpoint, timestamp, response identity, and tested deployment SHA.
- [ ] Do not change Render or Cloudflare settings or trigger a deployment as part of this checklist.

## Release decision

**Current decision: HOLD.** CI execution for the latest dependent commits and live-provider behavior remain unverified. Keep the PRs open and draft until evidence is available. No trade/order execution, wallet control, fund movement, or private-key functionality is in scope.
