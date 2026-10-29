# CIN Master Roadmap

**Project:** Crypto Intelligence Network (CIN)  
**Purpose:** A single numbered acceptance roadmap reconciled to the implementation evidence tracker.  
**Scope boundary:** Read-only public crypto intelligence, research, technical analysis, screening, forecasting, monitoring and alerts. No order execution, wallet control, private keys, or fund movement.  
**Working baseline:** 7 stages / 35 numbered steps. This is a practical delivery baseline, not a claim that every future product requirement has been exhaustively discovered. New requirements should be added explicitly rather than silently inflating progress counts.  
**Active work branch:** `feat/cin-market-data-row-provenance` (PR #66); the architecture-audit branch remains a separate Draft PR #8.  
**Release gate:** PRs #8, #65, and #66 remain open/unmerged; PR #11 was merged on 2026-10-26. No Render changes or deployment without fresh explicit user approval.

## Status meanings

- **Implemented — offline-tested:** code and automated tests exist; live-provider or production behavior is not implied.
- **Implemented — reconciled:** repository documentation and status controls are consolidated; this does not imply code, live-provider, or deployment validation.
- **Partial:** some implementation exists, with acceptance work still outstanding.
- **Pending:** capability or acceptance work is not established as complete.
- **Release-blocked:** requires live environment access and/or explicit deployment approval.

## Stage 1 — Repository foundation and safety boundary

1. **[Implemented — offline-tested]** Preserve official CIN identity and document read-only scope.
2. **[Implemented — offline-tested]** Keep public-data interfaces separate from exchange account/order capabilities.
3. **[Implemented — offline-tested]** Add controlled API errors and input validation for the existing public endpoints.
4. **[Implemented — offline-tested]** Maintain regression tests and the implementation evidence tracker.
5. **[Implemented — reconciled]** Establish one numbered roadmap, consolidate superseded checkpoint narratives, and distinguish the historical evidence ledger from current status.

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

When continuing work, choose the earliest unfinished step that can be completed safely in the repository without deployment approval. Update relevant tests and implementation evidence, refresh latest-head CI, then update this roadmap. Do not mark live or release checks complete based on offline tests.

## Current verification and evidence index (2026-10-30)

- **Current branch:** `feat/cin-market-data-row-provenance` (Draft PR #66).
- **Current verified head:** `6670db058163176fdc7d4222aa8fe2a62ccd2300`.
- **Exact-head CI:** all four configured workflows passed on this SHA: CIN Technical Analysis Tests (`40970346455`), CIN Automated Tests (`40970346454`), CIN screening checks (`40970346496`), and CIN evidence ingestion API checks (`40970346495`).
- **Step 6 increment:** deterministic provider-timestamp boundary tests cover 900/901-second freshness and 300/301-second future tolerance. This is offline evidence only; Step 6 remains Partial pending live-provider/deployed response verification.
- **Step 9:** candle interval/close-time and Kraken timestamp normalization regression work is recorded in Draft PR #27. Latest known PR head `23c6489121664d766c44de98ea40833f55a44e4e` passed its four configured workflows. Live Kraken compatibility remains unverified.
- **Step 10:** screening cache boundary tests are recorded in Draft PR #65; row-level provider/retrieval provenance is recorded in Draft PR #66. Live provider/cache behavior and deployed response metadata remain unverified.
- **Release controls:** PR #8, #65 and #66 remain Draft/open/unmerged; PR #11 is merged. Render is user-managed and was not changed or deployed.

## Historical evidence policy and Step 5 reconciliation (2026-10-30)

- The former dated checkpoint blocks have been removed from this active roadmap because they repeated superseded “pending CI” statements and obscured the current state.
- Detailed commit-by-commit history remains in `CIN_IMPLEMENTATION_TRACKER.md`. A historical “CI pending” entry describes only the state at the time it was written; it is not a current failure or current release status.
- This file is the only numbered roadmap (7 stages / 35 steps). The tracker is the detailed evidence ledger. `CIN_ARCHITECTURE_STATUS.md` is an architecture register, not a parallel roadmap.
- The active PR state and latest-head CI must be refreshed from GitHub before any future status report.
- **Step 5 reconciliation is complete:** the repository now has one authoritative numbered roadmap, the tracker is explicitly historical, and the architecture status is a register rather than a competing roadmap. The dated historical entries remain available as evidence but no longer act as current status. This documentation closure does not imply live validation or release readiness.

## Step 11 commodity evidence contract clarification (2026-10-30)

- Corrected the commodity-backed evidence API documentation to match the implemented and tested `max_age_days` contract: the accepted range is **0–3650 days**, not 1–3650.
- Existing offline API tests already cover the zero-day threshold, maximum threshold, strict integer typing, and invalid values.
- Step 11 remains Partial: CIN currently validates caller-supplied evidence metadata and freshness; it does not fetch issuer/reserve/custody documents or independently verify the underlying claims.
