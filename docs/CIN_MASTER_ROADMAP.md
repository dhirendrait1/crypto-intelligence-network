# CIN Master Roadmap

**Project:** Crypto Intelligence Network (CIN)  
**Purpose:** A single numbered acceptance roadmap reconciled to the implementation evidence tracker.  
**Scope boundary:** Read-only public crypto intelligence, research, technical analysis, screening, forecasting, monitoring and alerts. No order execution, wallet control, private keys, or fund movement.  
**Working baseline:** 7 stages / 35 numbered steps. This is a practical delivery baseline, not a claim that every future product requirement has been exhaustively discovered. New requirements should be added explicitly rather than silently inflating progress counts.  
**Active work branch:** `feat/cin-market-data-row-provenance` (PR #66); the architecture-audit branch remains a separate Draft PR #8.  
**Release gate:** PRs #8, #65, and #66 remain open/unmerged; PR #11 was merged on 2026-10-26. No Render changes or deployment without fresh explicit user approval.

## Status meanings

- **Implemented — offline-tested:** code and automated tests exist; live-provider or production behavior is not implied.
- **Partial:** some implementation exists, with acceptance work still outstanding.
- **Pending:** capability or acceptance work is not established as complete.
- **Release-blocked:** requires live environment access and/or explicit deployment approval.

## Stage 1 — Repository foundation and safety boundary

1. **[Implemented — offline-tested]** Preserve official CIN identity and document read-only scope.
2. **[Implemented — offline-tested]** Keep public-data interfaces separate from exchange account/order capabilities.
3. **[Implemented — offline-tested]** Add controlled API errors and input validation for the existing public endpoints.
4. **[Implemented — offline-tested]** Maintain regression tests and the implementation evidence tracker.
5. **[Partial]** Reconcile all legacy step references, duplicate roadmap notes, and acceptance evidence into this master roadmap.

**Exit gate:** all active modules remain read-only; no secrets, wallet control, or order execution are introduced.

## Stage 2 — Provider ingestion, provenance, and data quality

6. **[Partial]** Complete public market overview validation, including negative/non-finite values, optional-metric warnings, timestamp freshness, and controlled provider errors.
7. **[Implemented — offline-tested]** Harden public GitHub evidence metadata types, timestamps, partial metadata, freshness, and sanitized failures.
8. **[Implemented — offline-tested]** Harden public candle parsing for bounded responses, timestamps, OHLCV types, pair identity, duplicate conflicts, and requested result limits.
9. **[Partial]** Validate exchange candle interval alignment, future timestamps, and close-time consistency without rejecting legitimate market gaps.
10. **[Partial]** Complete provider provenance and stale-cache acceptance checks across screening and market-data responses.
11. **[Partial]** Validate commodity-backed token evidence against authoritative issuer, reserve, custody, redemption, and audit sources; never treat heuristic labels as proof.
12. **[Partial]** Validate provider behavior and documented rate-limit/fallback paths using authorized, read-only live smoke tests.

**Exit gate:** invalid, stale, missing, or conflicting evidence is surfaced explicitly; mocked CI is not described as live validation.

## Stage 3 — Screening and quantitative analysis

13. **[Implemented — offline-tested]** Keep deterministic technical analysis on supplied OHLC data with documented input contracts.
14. **[Implemented — offline-tested]** Maintain coin-screening identity deduplication, invalid-ID accounting, deterministic ranking, and numeric arithmetic guards.
15. **[Implemented — offline-tested]** Maintain derivatives snapshot validation for open interest, funding, mark/index price, and provider timestamps.
16. **[Partial]** Validate order-book depth quality, spread/imbalance methodology, and slippage-aware interpretation.
17. **[Partial]** Expand indicator edge-case tests and make indicator limitations and signal uncertainty clear to consumers.
18. **[Pending]** Add explicit cross-source conflict handling and evidence confidence rules where the same metric differs by source.

**Exit gate:** outputs are reproducible, provenance-backed, and avoid presenting incomplete data as confirmed signals.

## Stage 4 — Intelligence coverage and research evidence

19. **[Partial]** Complete public news search and low-confidence headline sentiment with multilingual/context limitations documented.
20. **[Pending]** Design authorized social-source ingestion for X, Reddit, and Telegram, respecting platform access limits.
21. **[Pending]** Define evidence-backed exchange-flow and whale-attribution methodology with clear identity uncertainty.
22. **[Partial]** Build source ingestion for commodity backing and growth fundamentals; distinguish claims from independently verified evidence.
23. **[Pending]** Define a verifiable evidence model for claims, citations, observation time, retrieval time, conflicts, and confidence.

**Exit gate:** CIN does not claim social sentiment, whale attribution, backing, or fundamentals are verified until sources and methods substantiate those claims.

## Stage 5 — Alerts, monitoring, and forecast evaluation

24. **[Pending]** Define user-configurable alert rules and threshold semantics.
25. **[Pending]** Implement deduplication, cooldowns, delivery-state tracking, and retry/error handling.
26. **[Pending]** Add an authorized alert delivery channel and keep credentials out of source control.
27. **[Pending]** Persist forecast timestamp, asset, price source, horizon, and target/invalidating conditions.
28. **[Pending]** Evaluate forecast outcomes and calibration with reproducible metrics and survivorship/look-ahead safeguards.
29. **[Partial]** Define monitoring health, freshness, provider outage, and stale-data warning states across services.

**Exit gate:** alerts and forecasts are auditable, repeat-safe, and evaluated after their horizons; no trading actions are triggered.

## Stage 6 — API integration and Android-friendly experience

30. **[Pending]** Define the mobile-first dashboard flow and API-to-screen mapping.
31. **[Pending]** Implement loading, empty, stale, partial, error, and source-provenance states consistently.
32. **[Pending]** Add accessible charts/tables for market overview, screening, technical analysis, derivatives, news, and alerts.
33. **[Pending]** Test small-screen layout, navigation, and low-bandwidth behavior.

**Exit gate:** the interface communicates uncertainty and freshness clearly and is usable on Android without implying unavailable capabilities.

## Stage 7 — Verification, release readiness, and handoff

34. **[Partial]** Keep all four CI workflows passing on the latest feature-branch head; review failures before counting a milestone as verified.
35. **[Release-blocked]** After fresh explicit approval, validate the target deployment revision, readiness/health endpoints, and read-only live smoke tests; do not merge or deploy before approval.

**Exit gate:** test evidence, live checks, deployed revision, known limitations, and rollback steps are documented; PR #8 remains unmerged until the user authorizes the release path.

## Consolidated implementation and verification record (2026-10-30)

This section replaces superseded checkpoint narratives that separately described intermediate commits as pending CI. Historical commit IDs remain in the implementation tracker; current status is governed by the numbered steps above and exact-head CI records below.

- **Current verified documentation head:** `92075a147bc64c0af3860b18ed01f821d1708232`. All four configured workflows passed on this exact head: CIN Technical Analysis Tests (`40970157697`), CIN Automated Tests (`40970157850`), CIN evidence ingestion API checks (`40970157709`), and CIN screening checks (`40970157715`).
- **Candle validation evidence:** PR #27 remains the offline interval-boundary test branch; latest known head `23c6489121664d766c44de98ea40833f55a44e4e` passed all four workflows. Kraken compatibility is tested with mocked timestamp fixtures only; live exchange behavior remains unverified.
- **Screening cache evidence:** PR #65 adds exact fresh-cache and stale-cache boundary tests. The PR remains Draft/open/unmerged; tests are offline.
- **Market-data provenance evidence:** PR #66 records provider identity and provider retrieval time per row and verifies endpoint serialization. Its latest documentation head is the current checkpoint above; all four workflows passed. This does not establish live provider correctness.
- **Release controls:** PR #8, #65 and #66 remain Draft/open/unmerged. PR #11 was merged on 2026-10-26. Render remains user-managed; no deployment was performed.
- **Verification boundary:** passing GitHub Actions means the configured automated checks passed on the exact listed commit. It does not establish live provider availability, production response behavior, or the currently deployed Render revision.

## Step 5 reconciliation notes (2026-10-30)

- The seven-stage / 35-step numbering in this document is the sole active roadmap baseline. Do not create parallel step numbering in status updates or treat historical implementation-log headings as roadmap steps.
- Historical intermediate CI entries that said “pending” or “must be refreshed” have been consolidated above; their old commit-specific results remain in `CIN_IMPLEMENTATION_TRACKER.md`.
- The tracker is the detailed implementation evidence ledger; this roadmap is the authoritative numbered scope/status view. Architecture status is a high-level architecture register, not a second roadmap.
- PR state is recorded in the repository reconciliation section below and should be refreshed from GitHub before future status claims.
- Step 5 remains Partial only for any remaining legacy references or duplicate milestone narratives outside this consolidated roadmap/tracker relationship. No release or live-provider work is implied.

## Operating rule

When continuing work, choose the earliest unfinished step that can be completed safely in the repository without deployment approval. Update the relevant tests and implementation evidence, refresh latest-head CI, then update this roadmap. Do not mark live or release checks complete based on offline tests.


## CI evidence refresh (2026-10-25)

All four configured workflows passed on checkpoint `1b847b843c14e0929f9ec972fbc36af14b70a356`. The tracker was subsequently clarified in commit `a9f7e96b4a86e7c139806feca312e407ecc32505`; CI on that new head must be refreshed. Live-provider behavior and production health remain unverified.


## Latest automated verification (2026-10-25)

All four configured workflows passed on code/documentation checkpoint `2c1f816d59bc4fa6aa1c31ce2ee01228cd46f29b`. The tracker was subsequently updated in commit `9a4dea4b00afe3fcf22d1335b8fc957539c6aad2` to record those results and the monthly-candle calendar-boundary caveat. CI must be refreshed for that newer tracker-only commit. Live-provider and deployment checks remain incomplete.

## Monthly candle freshness fix (2026-10-25)

- Implemented calendar-aware monthly duration for freshness thresholds using the latest closed candle open timestamp.
- Regression coverage includes leap-year February, common-year February, 30/31-day months, December year rollover, and the derived freshness threshold.
- Code: `5259bc9500068d577cba6bc617b9083ae92fdbc3`; tests: `b4d55897b08dc788e848b9273e4277dc31550702`; tracker: `59c421c11aad40c85ecf6263a8e70a76bdf102f9`.
- Latest-head CI is not yet verified. Open-time alignment, close-time consistency, live-provider behavior, and deployment checks remain unfinished.

## Candle boundary validation increment (2026-10-25)

- Binance candle boundary validation now checks close-time consistency, weekly Monday UTC anchoring, and monthly calendar boundaries; deterministic regression tests were added.
- Fixed-interval epoch alignment is not assumed without provider-specific evidence, 3-day anchoring remains provider-specific, and Kraken enforcement is deferred pending a compatibility pass.
- Code commits: `56b9578bba9df3b77168acf7051445ec924bfb15`, `0cb4e6efb60f4228142ceca005279afca54f3f39`; tests: `46e14b24f6c1ad98bb567bb4967242b41dd29f73`; tracker: `fd0f9c1b93c8f431ef679dc455df7d5e9b943366`.
- Latest-head CI is pending; live-provider and deployment checks remain outstanding.

## Latest-head CI and interval matrix verification (2026-10-25)

- Verified all four configured workflows passed on current Draft PR head `6367afc875e2084dbf25053aed8a0d23badc4227`:
  - CIN Technical Analysis Tests: [40143588595](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/40143588595)
  - CIN evidence ingestion API checks: [40143588598](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/40143588598)
  - CIN Automated Tests: [40143588591](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/40143588591)
  - CIN screening checks: [40143588616](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/40143588616)
- This head includes deterministic weekly Monday-UTC boundary tests and 3-day candle duration tests that intentionally avoid an unsupported epoch anchor assumption.
- These results establish offline CI only. Kraken boundary enforcement/compatibility, live provider behavior, and deployed service health remain unverified. PR #8 remains Draft and unmerged; no deployment or trading execution was performed.


## Latest-head verification refresh (2026-10-25)

- All four configured PR workflows passed on code/documentation head `540c886ef6b7dd2b07c4ff27cf8500070b4d58b7`:
  - CIN screening checks: [40146915587](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/40146915587)
  - CIN Automated Tests: [40146915579](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/40146915579)
  - CIN Technical Analysis Tests: [40146915637](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/40146915637)
  - CIN evidence ingestion API checks: [40146915576](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/40146915576)
- The head includes CoinGecko unexpected provider/parser failure containment and offline API regression tests.
- This verification is for the exact listed head only. It does not establish live-provider correctness or Render health. Any subsequent commit requires a fresh latest-head CI check.
- PR #8 remains Draft and unmerged. No Render configuration or deployment was changed.


## Step 10 offline acceptance refresh (2026-10-30)

- **Step 10 remains Partial.** Offline acceptance now covers both screening-cache policy and market-data row provenance; live-provider behavior and deployed responses remain unverified.
- Screening cache boundary tests are in Draft PR #65: fresh-cache TTL includes the exact 90-second boundary; refresh is attempted one second beyond it; stale cache is accepted at exactly 900 seconds and rejected one second beyond that limit when refresh fails. These are deterministic offline tests, not provider observations.
- Market-data provenance is in Draft PR #66. Each normalized row records `provider: "CoinGecko"` and a timezone-aware `provider_retrieved_at`; the endpoint regression test verifies these row-level fields survive in `data[]` and remain distinct from the API response's own `retrieved_at`.
- PR #66 latest verified head: `01fa12d0699359637280a098d4fc4a1bf13b3cc4`. All four workflows passed on this exact head: screening (run `40969401819`), offline API safety (run `40969401886`), offline technical analysis (run `40969401799`), and Render scaffold validation (run `40969401887`).
- Both PRs remain Draft/open/unmerged. No production provider selection, cache acceptance rule, Render setting, or deployment was changed by this increment.
- Remaining Step 10 acceptance: confirm live provider provenance and cache behavior under authorized read-only conditions, then verify deployed response metadata. Offline CI must not be represented as live verification.


## Repository reconciliation checkpoint (2026-10-30)

- PR #11 (`integrate/cin-audit-mainline`) is merged; the implementation tracker’s prior statement that it was awaiting merge is historical and has been corrected at its release-controls header.
- PR #8 remains Draft/open. PR #65 and PR #66 remain Draft/open and unmerged.
- PR #66’s roadmap evidence update is commit `8ea7709c5f170a8161d819f08e177e15fe7d34d7`; all four workflows passed on that exact commit (runs `40969923757`, `40969923901`, `40969923853`, `40969923779`).
- This checkpoint records repository/CI state only. Render remains user-managed and has not been changed or deployed as part of this work.

## Step 6 market-data timestamp boundary coverage (2026-10-30)

- Made the market-data timestamp assessment clock injectable and deterministic for validation; a naive injected clock produces an explicit `unknown` status rather than silently assuming UTC.
- Added exact-boundary regressions: provider timestamp age 900 seconds is fresh; 901 seconds is stale; a timestamp exactly 300 seconds in the future is tolerated as fresh with age zero; 301 seconds in the future is unknown.
- This increment extends Step 6 offline validation only. Live CoinGecko freshness behavior and deployed API responses remain unverified; Step 6 therefore remains Partial.
- Code/test commits: `f7cf8fa5518eff6c64f6659abc66d74641ee8d81` and `67675b4f043e29aa21cfc824199656bc3cee83eb`. Latest-head CI is pending and must pass on the final documentation commit before this increment is counted as verified.
