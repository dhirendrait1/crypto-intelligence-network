# CIN Master Roadmap

**Project:** Crypto Intelligence Network (CIN)  
**Purpose:** A single numbered acceptance roadmap reconciled to the implementation evidence tracker.  
**Scope boundary:** Read-only public crypto intelligence, research, technical analysis, screening, forecasting, monitoring and alerts. No order execution, wallet control, private keys, or fund movement.  
**Working baseline:** 7 stages / 35 numbered steps. This is a practical delivery baseline, not a claim that every future product requirement has been exhaustively discovered. New requirements should be added explicitly rather than silently inflating progress counts.  
**Branch:** `feat/cin-architecture-audit`  
**Release gate:** PR #8 stays Draft/unmerged; no Render changes or deployment without fresh explicit approval.

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
18. **[Partial — contract specified; implementation and acceptance tests pending]** Add explicit cross-source conflict handling and evidence confidence rules where the same metric differs by source.

### Step 18 acceptance contract — cross-source conflicts

- **Compare like with like:** normalize asset identity, metric name, quote currency/unit, observation interval, market venue/scope, and observation timestamp before comparing values. Never compare USD with USDT, spot with derivatives, or different intervals as if they were equivalent.
- **Preserve source observations:** retain each candidate value with provider/source ID, asset/metric identity, unit, venue/scope, observed-at timestamp (timezone-aware), retrieved-at timestamp, freshness state, and any transformation applied. Do not silently overwrite a source observation with another.
- **Classify the outcome:** use `agreement`, `material_conflict`, `insufficient_comparable_data`, or `stale_or_unknown`. Missing values are not zero. A provider failure is not evidence that another source is correct.
- **Use metric-specific tolerances:** define and test tolerances per metric and unit; do not apply one global percentage to prices, volumes, funding, open interest, and supply metrics. Make the threshold visible in the result metadata.
- **Choose only by declared policy:** if one source is designated preferred for that exact metric and passes identity, freshness, schema, and quality checks, it may be selected with the selection reason exposed. Otherwise return the conflict and candidates without inventing a winner. Never average incompatible observations.
- **Confidence is evidence quality, not probability:** explain confidence using source quality, freshness, completeness, comparability, and independent corroboration. Do not describe an uncalibrated score as a probability, verified fact, or investment recommendation.
- **Keep outputs auditable:** include the rule/version used, candidate sources, conflict classification, and reason codes in API output or structured diagnostics; sanitize provider errors and exclude credentials.
- **Fail safely:** material unresolved conflicts must lower confidence or block derived conclusions for that metric; downstream screening/analysis must not silently consume a conflicted value as confirmed.
- **Regression acceptance:** test identical values; within-tolerance differences; beyond-tolerance conflict; mismatched asset/quote/unit/venue/interval; stale versus fresh observations; missing/invalid timestamps; duplicate source records; provider errors; deterministic ordering; and ensuring missing is not treated as zero.
- **Scope:** read-only public data only. No order execution, wallet access, custody, fund movement, or private-key handling. Offline tests establish deterministic logic only; live provider behavior requires separate authorized smoke tests.

**Exit evidence required before marking implemented:** a documented metric-specific policy, deterministic implementation, automated conflict/regression tests, API contract examples, and explicit separation between offline CI and live-source validation.

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

## Current checkpoint (2026-10-25)

- Latest CI-verified code/documentation checkpoint before this tracker clarification: `1b847b843c14e0929f9ec972fbc36af14b70a356`.
- All four workflows passed on that checkpoint: CIN Automated Tests (`40142830679`), CIN screening checks (`40142830668`), CIN Technical Analysis Tests (`40142830721`), and CIN evidence ingestion API checks (`40142830681`). A later tracker-only clarification records remaining live and interval-boundary acceptance gaps.
- The CI results establish automated test success only; they do not establish live-provider correctness or deployed service health.
- PR #8 is Draft and unmerged. No Render changes or deployment were performed.
- **Do not report a single completion percentage:** step statuses mix implemented modules, partial acceptance work, future capabilities, and an approval-blocked release gate. Count by status only after refreshing this roadmap against the current head and CI evidence.

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
