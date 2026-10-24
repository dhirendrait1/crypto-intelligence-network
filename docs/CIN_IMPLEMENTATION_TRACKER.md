# CIN Implementation Evidence Tracker

**Scope:** Crypto Intelligence Network (CIN), read-only research, analysis, forecasting, monitoring, and alerts. This tracker records what is supported by repository evidence; it is not a claim that CIN is production-complete.

**Branch:** `feat/cin-architecture-audit`  
**Release restrictions:** Do not merge PR #6, #7, or #8; do not modify Render or trigger deployment without fresh explicit approval. No order execution, wallet control, private keys, or fund movement.

## Status definitions

- **Implemented, offline-tested:** Code and automated tests exist; live-provider behavior and deployed revision are not thereby certified.
- **Partial:** Some implementation exists, but required data sources, coverage, or verification are incomplete.
- **Not established:** Repository evidence does not establish a complete end-to-end capability.
- **Release-blocked:** A safe release requires deployment authorization or live environment access that is not currently available.

## Capability inventory

| Capability | Repository evidence | Current status | Remaining acceptance work |
|---|---|---|---|
| Public market overview | `market_data_step1.py`; `tests/test_market_data_step1_validation.py` | Partial / offline-tested | Reject non-finite/negative prices; omit invalid optional metrics with warnings; per-row provider timestamp freshness (`fresh` ≤15 minutes, `stale` >15 minutes, `unknown` for missing/invalid/future timestamps); controlled unexpected-status errors; CI regression coverage |
| Coin screening | `coin_screening_step2.py`, screening API tests | Implemented, offline-tested | Live provider smoke test; confirm fresh/cache/stale metadata in running service |
| Screening source provenance | Provider retrieval timestamps, cache age, structured primary/fallback failures, stale warning; fresh/live, fresh-cache, and stale-cache response regression tests | Implemented, offline-tested on feature branch | Live read-only smoke test remains unverified; outbound network access from this environment is unavailable |
| Commodity-backed token scan | CoinPaprika public ticker scan, bounded stale cache, structured provider errors, separate retrieval metadata retained even when no assets match | Partial / offline-tested | Classification is heuristic; independently validate issuer, custody, reserves, redemption and audit evidence; live provider behavior remains unverified |
| FDV calculation safety | CoinPaprika FDV uses price and positive max supply; does not substitute total supply | Implemented, offline-tested | Continue provider-schema monitoring and live checks |
| Commodity backing assessment | Caller-supplied evidence metadata API | Partial | Ingest and verify authoritative evidence; do not treat submitted claims as independently verified |
| Growth fundamentals assessment | Caller-supplied evidence metadata API | Partial | Source ingestion, timestamped evidence, conflict handling, independent verification |
| Public evidence ingestion | Allowlisted public GitHub metadata for three Ethereum-related repositories; repository identity type-checked; counters must be non-negative integers (booleans rejected); timestamps must be ISO-formatted with explicit timezone; missing optional fields are surfaced as `metadata_partial`; malformed payloads raise controlled source errors; offline regression tests | Partial / offline-tested | API boundary regression tests cover unexpected provider-shape and runtime exceptions returning a sanitized HTTP 502; freshness policy implemented: fresh ≤7 days, stale >7 days, unknown when timestamps are unavailable; timestamps >5 minutes in the future are rejected; tests are mocked/offline and live source behavior remains unverified; not a general news/social connector |
| Technical analysis from supplied OHLC | `cin_technical_analysis.py` and API | Implemented, offline-tested | Validate additional edge cases and documented indicator contracts |
| Exchange-backed market candles | `cin_public_market_candles_api.py`; closed-candle filter; volume forwarding; unsupported interval rejection | Partial / offline-tested | Live exchange smoke checks, provider-specific symbol mapping and rate-limit handling |
| Derivatives snapshot (OI, funding, mark/index price) | `cin_derivatives_market_data_api.py`; read-only Binance USDⓈ-M public endpoints; provider timestamps, retrieval time, OI change from latest two 4h aggregates; invalid/missing data states; scaffold router registration and offline regression tests | Implemented, offline-tested | Single-exchange coverage; live provider smoke test; liquidations remain explicitly unavailable pending continuous event ingestion and aggregation |
| Order-book depth / liquidity | Included in `cin_derivatives_market_data_api.py` as a public Binance depth snapshot with per-side valid level counts, retrieval timestamp, spread, and bid/ask notional imbalance; crossed books rejected | Partial / offline-tested | Live snapshot validation, multi-exchange coverage and slippage-aware depth methodology |
| Exchange flows / whale attribution | No complete end-to-end capability established | Not established | Define verifiable sources and attribution limitations; avoid unsupported whale claims |
| Public news search and headline sentiment | `cin_public_news_sentiment_api.py`; GDELT DOC public article search; URL deduplication, provider article-time preservation, explicit low-confidence keyword sentiment, structured provider failures, scaffold route registration and offline regression tests | Partial / offline-tested | Live source validation; improve multilingual/context handling; this is news, not X/Reddit/Telegram sentiment |
| Social-platform sentiment (X, Reddit, Telegram, etc.) | No complete end-to-end capability established; news headlines are not social sentiment | Not established | Identify public/authorized sources, respect access limits, deduplicate posts, preserve timestamps and uncertainty; no unsupported social claims |
| Alerts and monitoring | No complete end-to-end capability established | Not established | Rules, delivery channels, deduplication, cooldowns, delivery-state tracking |
| Forecast outcome tracking | No complete end-to-end capability established | Not established | Store forecast timestamp, horizon, price source, outcome calculation and calibration metrics |
| Dashboard / Android-friendly UX | No complete end-to-end capability established by the source inventory | Not established | Define user flows, API integration, accessibility, loading/error/stale states |
| Production release validation | Current Render revision has not been confirmed against feature-branch code; public smoke check was inaccessible from the current web access path | Release-blocked | Explicit release authorization, then controlled deployment and health/readiness/live smoke validation |

## Market-data freshness audit checklist

- [x] Preserve provider timestamp separately from CIN retrieval timestamp.
- [x] Expose top-level cache age for non-empty screening results.
- [x] Preserve primary and fallback provider error kinds and HTTP status.
- [x] Test stale-cache screening response warning and structured provider details.
- [x] Test fresh screening response metadata.
- [x] Add bounded stale-cache fallback for commodity scans after HTTP, network, and invalid-response failures.
- [x] Add tests for commodity stale-cache provenance and endpoint serialization.
- [x] Preserve commodity scan timestamp and scanned-universe counts when zero assets match; cache empty scans with separate metadata.
- [x] Test read-only derivatives snapshot parsing, provider timestamps, open-interest change, missing liquidation state, and network-failure classification.
- [x] Add read-only order-book spread/depth metrics with retrieval timestamp, per-side valid-level counts, and crossed-book rejection tests.
- [x] Add public GDELT news search with URL deduplication, source timestamps, explicit low-confidence headline sentiment, provider-failure tests, and scaffold router registration.
- [x] Add scaffold CI checks for the news regression suite and expected read-only route registrations.
- [x] Register the derivatives router in the scaffold patch and run its regression tests in scaffold CI.
- [x] Verify all four workflows on commit `26b65c7868fb1393feb6ff1fb7a24ab35f4e5a94` (screening, automated tests, technical analysis, evidence ingestion). Results are mocked/offline tests; the derivatives snapshot tests are included in the automated scaffold workflow.
- [ ] Perform live read-only provider smoke tests for screening, candles, and derivatives; compare provider timestamps, CIN retrieval time, cache age, and stale warning. Attempted from this environment using available public fetch paths, but the Render service endpoints were inaccessible and outbound DNS resolution had previously failed; this is an environment limitation, not evidence that Render or the providers are down.
- [ ] Confirm the running Render service serves the tested code revision; do not deploy without explicit approval. This cannot be established from the current network-restricted environment.

## Completion accounting

Do **not** calculate a single completion percentage from this inventory: it mixes implemented modules, partially specified capabilities, and future capabilities. A defensible count requires a user-approved numbered product requirements baseline and a one-to-one mapping from each requirement to acceptance evidence. This tracker is a source-inventory baseline, not that missing requirements baseline.


## Commodity evidence metadata hardening (2026-10-24)

- [x] Validate evidence URLs as absolute HTTP(S) URLs with a hostname; reject scheme-only URLs and embedded credentials.
- [x] Downgrade caller-supplied `verified` metadata when publication or review timestamps are in the future.
- [x] Downgrade caller-supplied `verified` metadata when the review timestamp precedes publication.
- [x] Return explicit `source_url_valid` and `timestamp_validation_errors` metadata for auditability.
- [x] Add offline regression tests for URL and timestamp chronology edge cases.
- [x] Reject timezone-naive publication/review timestamps instead of silently assuming UTC; regression coverage added for both commodity and growth evidence.
- [x] Verify the new regression tests and all four repository workflows on commit `7e26219dc57b752255f6e58e8aefdf1f28e749e1`; all four workflows passed. These are offline/mocked tests, not live provider validation.
- **Boundary:** these checks validate supplied metadata only. CIN still does not fetch source documents or independently certify reserve, custody, solvency, or redemption claims.


## Growth fundamentals evidence validation (2026-10-24)

- [x] Audit the current assessment contract and confirm the coverage score measures submitted evidence metadata, not project quality or investment merit.
- [x] Require absolute HTTP(S) URLs with a parsed hostname rather than accepting a scheme-prefix string.
- [x] Add regression tests for scheme-only URLs, URLs without a hostname, and valid HTTP URLs.
- [x] Verify all four GitHub Actions workflows on commit `31f8ad04051e15ef028d85ee58f0dd79e2826b9f`; all passed. Results are offline tests only.
- [x] Downgrade supplied `verified` growth-fundamentals records with future publication timestamps to `unverified`; regression test added.
- [x] Require explicit timezone offsets for growth publication timestamps; naive timestamps are treated as missing and cannot support `verified` status.
- [x] Require explicit timezone offsets for commodity publication/review timestamps; naive timestamps are treated as missing and cannot support `verified` status.

These are timestamp sanity checks on caller-supplied metadata, not independent source verification.
- [x] Surface mixed evidence statuses as `conflicting` at category/type level; summaries no longer let one supplied `verified` record hide other stale, unavailable, or unverified records. Regression tests added for commodity and growth assessments.
- [x] Harden assessment input contracts: malformed non-object records are retained as unverified audit rows, non-list input cannot be interpreted as verified coverage, and unknown growth categories are surfaced in counts and prevent a complete overall status.
- [x] Validate freshness thresholds in commodity and growth assessments; invalid thresholds fall back to the documented 90-day default and are flagged in output.
- [x] Validate injected assessment clocks: timezone-naive or non-datetime clocks fall back to current UTC and are flagged; future publication timestamps no longer receive a misleading age of zero, and growth rows expose timestamp validation errors.
- [x] Report duplicate evidence rows and count normalized source/timestamp identities once in category coverage; raw rows remain available for audit and differing statuses still surface as conflicts.
- [x] Validate caller-supplied assessment clock values; reject naive/non-datetime clocks by falling back to the system UTC clock and expose `assessment_clock_valid` in response metadata.
- [x] Do not report future-dated evidence as having a non-negative publication age; expose timestamp validation errors for growth-fundamentals records.
- [x] Bound assessment API symbols, evidence batch sizes, metadata field lengths, and freshness thresholds; reject unknown fields and non-integer/boolean thresholds at the request boundary.
- [x] Add direct assessment-level regression tests ensuring booleans and floats are rejected as integer freshness thresholds (safe 90-day fallback, explicitly flagged); all four workflows passed on test commit `87e37bb1bee73628bc2b47f80f903cec27ddf55b`.
- [x] Align growth URL validation with commodity validation by rejecting embedded URL credentials; add offline regression tests.
- [ ] Add source-aware conflict resolution and independent source retrieval; current conflict detection compares supplied statuses and does not establish which source is authoritative.


- Follow-up validation note: the latest intermediate PR workflow exposed a commodity assessment clock-scope regression in the merged test snapshot. Do not mark this clock-hardening batch release-ready until a fresh workflow run confirms all four workflows pass on the corrected revision.

## Assessment API boundary validation (2026-10-24)

- [x] Restrict commodity-backed and growth-fundamentals request symbols to bounded alphanumeric identifiers with only `.`, `_`, or `-` after the first character; reject whitespace and pair-style separators.
- [x] Require `max_age_days` to be a strict integer in the documented 0–3650 range; booleans are not accepted as integers, and a zero-day freshness window is valid.
- [x] Add regression tests for malformed symbols, boolean thresholds, zero-day thresholds, and oversized growth-evidence batches.
- [x] Confirm the assessment API/news-query regression suite and all four CI workflows pass on revision `0925c3c39c300d29bade9e0b2ffa7071e5370704`; tests are offline/mocked, not live-provider validation.
- **Boundary:** these checks validate API request shape. Evidence publication timestamps remain strings at the request boundary so malformed or unverifiable source metadata can be retained as unverified audit evidence rather than being mistaken for verified claims.

- News endpoint hardening: reject a whitespace-only query after normalization with HTTP 422 before provider access; regression test added.

- [x] Hardened injected assessment clocks in commodity and growth evidence assessment functions: naive/non-datetime clocks are rejected and safely replaced with current UTC; future publication dates return no misleading nonnegative age and growth rows expose timestamp errors. Regression coverage is present in both assessment test suites.
- [x] Re-ran all four workflows on commit `6455ca486d0883914150cf1c1d518dad19c058d7`; screening, evidence-ingestion API, automated scaffold tests, and technical-analysis workflows all passed. An earlier intermediate revision failed because the commodity clock-validation edits had not yet landed together; the later clean run passed. These remain offline/mocked checks, not live-provider validation.

- [x] Keep injected-clock validity consistent at assessment and evidence-row level for commodity and growth assessments; add regression coverage for timezone-naive clocks. All four workflows passed on commit `5d1539492ef93dff081af807463b696a9da4cedb` (CIN Automated Tests, screening, technical analysis, evidence-ingestion API). Tests are offline/mocked; no live provider or production validation is implied.

- [x] Follow-up on 2026-10-24: an intermediate commodity clock propagation commit (`a1a9e2b`) failed screening tests because `current`/`assessment_clock_valid` were not scoped in `assess_commodity_asset`. The corrected branch snapshot defines and validates the assessment clock in the assessment function and propagates it to evidence rows. All four workflows passed on test commit `87e37bb1bee73628bc2b47f80f903cec27ddf55b`; this is offline/mocked validation, not live-provider or production verification.

## Public candle provider boundary hardening (2026-10-24)
- [x] Added catch-all handling for unforeseen Binance parser/provider exceptions and Kraken fallback exceptions; these return controlled 502/503 responses rather than uncaught 500s. Added `AttributeError` and generic `Exception` regression cases; all four workflows passed on commit `546b5d4b34941a0567c1869fb83baa3ad86feb54`. Offline/mocked validation only.

- [x] Audit public candle provider parsing and error translation for unexpected provider response exceptions.
- [x] Convert unexpected provider runtime/type/shape and invalid UTF-8 failures into a sanitized HTTP 502 instead of leaking an uncaught exception to the API boundary.
- [x] Convert equivalent Kraken fallback failures after Binance HTTP 451 into a controlled HTTP 503 with a generic fallback-unavailable message.
- [x] Add mocked regression tests for provider runtime errors, invalid UTF-8, malformed payload type, and fallback runtime failure.
- [x] Verify all four repository workflows on commit `63b81046f252f293a4be952b28447b1417df6c1b`; screening, evidence-ingestion API, technical analysis, and automated scaffold tests all passed.
- **Boundary:** provider checks are mocked/offline. They do not establish live exchange availability, source correctness, or production deployment health.

## Derivatives API symbol validation (2026-10-24)

- [x] Tighten the public derivatives snapshot query parameter to the alphanumeric symbol format already used by the public candle API; reject underscore-bearing malformed symbols during FastAPI request validation rather than forwarding them to the provider.
- [x] Add a regression assertion for the published OpenAPI parameter pattern and bounds.
- [x] All four workflows passed on commit `86ed2e5682e86b490a1310d517ff272aa373f28a`: CIN Automated Tests (`40106663241`), evidence ingestion API checks (`40106663312`), Technical Analysis Tests (`40106663239`), and screening checks (`40106663252`). Validation is offline/mocked; no live provider or production verification is implied.

## Derivatives provider error handling (2026-10-24)

- [x] Added a final catch-all at the read-only derivatives API boundary so unexpected provider/parser exceptions are sanitized as HTTP 502; added `AttributeError` and generic `Exception` regression cases. All four workflows passed on commit `10dc7ee845d2184dadb660333b921202361f1ae9` (offline/mocked tests only).
- [x] Unexpected provider runtime/type/shape errors and invalid UTF-8 are mapped to a sanitized HTTP 502.
- [x] Added mocked regression tests for these failure classes.
- [x] Screening, evidence-ingestion API, and technical-analysis workflows passed on revision f789b282be76d59598778b4e891b61efb34475b3.
- [x] All four workflows subsequently confirmed on that exact revision: CIN Automated Tests, screening checks, technical-analysis tests, and evidence-ingestion API checks all passed.
- Boundary: offline/mocked validation only; no live provider or deployment verification.

## News provider boundary tests
- [x] Added catch-all sanitization for unforeseen GDELT provider/parser exceptions as HTTP 502, with `AttributeError` and generic `Exception` regression cases; all four workflows passed on commit `13ec8555ac6b6f744d14afbb9c22500f77ba99c4`. Offline/mocked validation only.
- [x] Hardened GDELT article URL parsing to accept only absolute HTTP(S) URLs with a hostname, no embedded credentials, and no whitespace/control characters; added malformed URL regression cases. All four workflows passed on commit `349c21fbcc8e658c8e70f3fad2586846319dd914`; validation is offline/mocked and does not establish live GDELT behavior.
- [x] Sanitized unexpected provider runtime/type/UTF-8 errors as HTTP 502; mocked regression tests added.
- [x] Four workflows passed on commit 6826048f92e825a33e3503d33628d913df10507d.
- Boundary: offline tests only; live GDELT and production behavior remain unverified.


## Assessment API payload size bounds (2026-10-24)

- [x] Added maximum lengths for caller-supplied commodity and growth evidence fields (type/category, source name, URL, timestamps, status, notes) to prevent oversized individual metadata strings reaching assessment logic.
- [x] Added offline regression tests for over-limit fields in both assessment request models; existing symbol, evidence-batch, and strict freshness-threshold bounds remain in place.
- [x] All four CI workflows passed on code/test commit `1f42a825530d60752c2294fd8c6d298faa68932d` (CIN Automated Tests, screening checks, technical-analysis tests, and evidence-ingestion API checks). Validation is offline/mocked, not live-provider or production verification.
- **Boundary:** validation constrains request size/shape only. It does not authenticate source URLs, prove source content, or independently verify the underlying evidence claims.


## Evidence URL syntax hardening (2026-10-24)

- [x] Commodity and growth evidence URL validators now reject raw whitespace and control characters before URL parsing, in addition to requiring HTTP(S), a hostname, and no embedded credentials.
- [x] Added regression tests for newline, tab, and raw-space URL inputs; growth assessments now expose explicit `source_url_valid` metadata for audit consistency.
- [x] All four workflows passed on final code/test commit `bdfce86b7608b2207693b50d59aeccf92796794c` (automated tests, screening checks, technical-analysis tests, evidence-ingestion API checks). An intermediate test-string escaping issue was corrected before this successful run.
- **Boundary:** syntactic URL validation does not fetch the URL, verify source ownership, or certify evidence claims.


## Public evidence ingestion request validation (2026-10-24)

- [x] Added explicit symbol and repository-path format constraints to the public evidence ingestion request model; unsupported but well-formed symbols still receive the existing controlled API error, while malformed shapes fail request validation.
- [x] Added offline tests for whitespace/separator-bearing symbols and malformed repository paths.
- [x] All four workflows passed on code/test commit `ce511118dd4416fd74d25440266a76b01d785b4c`: CIN Automated Tests, screening checks, technical-analysis tests, and evidence-ingestion API checks. Tests are offline/mocked.
- **Boundary:** the repository allowlist remains authoritative; syntactic path validation does not permit arbitrary repository fetches.


## News URL control-character parity (2026-10-24)

- [x] Extended GDELT article URL validation to reject DEL (ASCII 127) as well as whitespace and lower control characters; added newline, tab, and DEL regression cases.
- [x] All four workflows passed on code/test commit `4fd998d23fa1f8cc0b9c78765933a2775a9cf7bd` (automated tests, screening, technical analysis, evidence-ingestion API checks). Validation is offline/mocked.
- **Boundary:** this validates article-link syntax only. It does not prove the publisher is trustworthy or validate the article's claims.

## Strict API payload contracts (2026-10-24)

- [x] Reject unknown top-level fields and nested evidence fields in commodity-backed and growth-fundamentals assessment requests.
- [x] Reject unknown fields in public evidence ingestion requests instead of silently ignoring misspellings or unsupported keys.
- [x] Follow-up API-boundary audit: test strict freshness-threshold validation against floats, numeric strings, booleans, negative values, and out-of-range values across commodity and growth request models. All four workflows passed on test commit `f330510cc6a4db7ac948a487dc857979c3ac5eec` (runs `40106537667`, `40106537653`, `40106537650`, `40106537648`). Offline/mocked CI only.
- [x] Add offline regression tests for unknown fields at each API boundary.
- [x] All four workflows passed on test commit `da7d1fd2b0b1928fdc90f6396ce3c02e10d70ed7`: CIN Automated Tests, screening checks, technical-analysis tests, and evidence-ingestion API checks.
- **Boundary:** these checks validate request shape only. They do not authenticate submitters, fetch caller-provided evidence URLs, or independently verify claims. CI is offline/mocked and does not certify live providers or production deployment.

- [x] Validate the injected assessment clock before using it in commodity/growth evidence calculations; reject naive/non-datetime test clocks safely, expose the validity flag, and avoid reporting future publication ages as zero.
- [x] Correct commodity assessment clock propagation so endpoint callers and malformed injected-clock tests do not raise unexpected `NameError` / `AttributeError` exceptions; preserve the invalid-clock audit flag on normalized rows.
- [x] Correct commodity clock propagation so normalized evidence rows use the validated UTC assessment clock rather than the raw injected value. All four workflows passed on commit `d829699ac591e2ef6b430ae274108a844f576eef`: CIN screening checks (run `40106430183`), CIN Automated Tests (`40106430190`), evidence ingestion API checks (`40106430187`), and Technical Analysis Tests (`40106430182`). These are CI regression tests, not live-provider or production verification.

## Public API symbol-bound consistency (2026-10-24)

- [x] Cross-checked the public candle and derivatives snapshot request contracts.
- [x] Reduced the derivatives symbol maximum length from 30 to 20 characters to match the public candle API's accepted alphanumeric pair length; kept the existing 5-character minimum and alphanumeric pattern.
- [x] Updated the derivatives OpenAPI regression test to assert the 20-character bound and added the same documented alphanumeric pattern/minimum/maximum constraints to both public candle routes.
- [x] Added OpenAPI regression coverage for `/market-candles` and `/technical-analysis/market`; all four workflows passed on test commit `5ee26c102a6dafe978024e3ad9c436ebe8f525d0`: CIN Automated Tests (run `40107312372`), screening checks (run `40107312395`), Technical Analysis Tests (run `40107312379`), and evidence-ingestion API checks (run `40107312427`).
- **Boundary:** the shared format is a syntactic guard, not proof that a pair is listed by Binance or Kraken. Validation remains offline/mocked; no live-provider or production check is implied.

## Technical-analysis API error contract (2026-10-24)

- [x] Audited the public candle endpoint's technical-analysis exception boundary.
- [x] Replaced exception-text leakage for invalid analysis input with a stable HTTP 502 detail and added a sanitized HTTP 502 fallback for unexpected runtime/parser exceptions.
- [x] Added an offline regression test that injects an unexpected analysis runtime failure and asserts internal exception text is not returned.
- [x] All four workflows passed on code/test commit `848d0b949c05f3cce4440e790c0361f071d1f2ce`: CIN Automated Tests (run `40107210314`), screening checks (run `40107210327`), Technical Analysis Tests (run `40107210326`), and evidence-ingestion API checks (run `40107210319`).
- **Boundary:** the regression uses mocked candle data and an injected exception. It does not verify live exchange behavior or production deployment.


## Evidence URL port validation (2026-10-24)

- [x] Tightened commodity and growth evidence URL syntax checks by forcing URL parser port validation; malformed non-numeric ports and out-of-range ports are rejected instead of being treated as valid HTTP(S) source metadata.
- [x] Added regression cases for `https://example.com:notaport/report` and `https://example.com:99999/report` in both assessment test suites.
- [x] All four workflows passed on revision `5657b19942f44c587fac396f2e375b36468fdf9d`: screening checks (run `40108389592`), technical-analysis tests (run `40108389595`), evidence-ingestion API checks (run `40108389626`), and automated scaffold tests (run `40108389597`). Offline/mocked CI only.
- **Boundary:** URL syntax validation does not fetch a source, confirm its ownership, or independently verify the underlying evidence claim.

- [x] Follow-up URL syntax audit: commodity backing, growth fundamentals, and GDELT article URLs now reject non-numeric and out-of-range explicit ports by forcing parser port validation; regression cases added to all three test suites. This prevents malformed ports from being accepted as valid source links.
- **Boundary:** URL parsing still does not fetch articles or verify publisher identity/claim accuracy.

## Assessment-clock regression follow-up (2026-10-24)

- [x] Corrected commodity assessment clock propagation and ensured the summary exposes `assessment_clock_valid` once, with the validated UTC clock passed into each evidence row.
- [x] Added regression coverage asserting valid clock metadata appears consistently in the commodity summary and normalized evidence rows.
- [x] All four workflows passed on revision `1020ee7c9aeebdd3fc461215dbe474362faf8146`: CIN Automated Tests (run `40108896479`), screening checks (run `40108896505`), evidence-ingestion API checks (run `40108896477`), and Technical Analysis Tests (run `40108896530`).
- **Boundary:** these are automated offline/mocked regression checks. They do not verify live providers or the deployed Render service; no merge or deployment was performed.

## Public news timestamp provenance (2026-10-24)

- [x] Preserve GDELT's original `seendate` in `published_at` while adding `published_at_utc` and `published_at_validation_status` so malformed, missing, or timezone-naive provider timestamps are not silently treated as valid times.
- [x] Add offline regression tests for GDELT compact UTC timestamps, malformed timestamps, timezone-naive ISO timestamps, and missing timestamps.
- [x] All four workflows passed on code/test revision `bf896c485891b39e972a4e538ed584ba1716d79a`: evidence-ingestion API checks (run `40109030489`), CIN Automated Tests (run `40109030510`), Technical Analysis Tests (run `40109030524`), and screening checks (run `40109030475`).
- **Boundary:** timestamp parsing validates format and timezone presence only; it does not independently confirm publisher accuracy, article truth, or live GDELT reliability.

## Public news duplicate URL normalization (2026-10-24)

- [x] Canonicalize article URL identity for deduplication by normalizing scheme/hostname case, removing fragments and default ports, and treating a trailing slash as equivalent for duplicate detection; keep the first provider URL unchanged in output.
- [x] Added a regression case for a duplicate article URL with uppercase hostname, default HTTPS port, trailing slash, and fragment.
- [x] All four workflows passed on code/test revision `60b85f65f93f9d8d17cfb7650c20a61b73675c0f`: screening checks (run `40109111387`), CIN Automated Tests (run `40109111425`), Technical Analysis Tests (run `40109111492`), and evidence-ingestion API checks (run `40109111444`).
- **Boundary:** URL normalization reduces duplicate entries but does not prove two publishers' content is equivalent or establish article accuracy.

## Evidence identity canonicalization follow-up (2026-10-24)

- [x] Corrected commodity and growth evidence deduplication so URL identity normalizes scheme/hostname case, default ports, fragments, and trailing slashes without lowercasing case-sensitive paths or query strings.
- [x] Normalize parseable timezone-aware publication/review timestamps to UTC identity, so equivalent instants with different offsets deduplicate consistently.
- [x] Invalid/credential-bearing URLs retain their literal identity rather than being canonicalized into a valid URL's identity; IPv6 hosts remain bracketed when canonicalized.
- [x] Added offline regressions for host case/default port/fragment/trailing slash/timezone-offset equivalence and for distinct case-sensitive paths.
- [x] All four workflows passed on code/test revision `cee4f1bd9b4a61bf9b63bb12e451254884d4451d`: evidence-ingestion API checks (run `40110072726`), CIN Automated Tests (`40110072860`), screening checks (`40110072796`), and Technical Analysis Tests (`40110072728`). Job-level results were checked and each concluded `success`.
- **Boundary:** tests are offline/mocked and do not independently verify evidence claims or source contents. No merge or production deployment was performed.

## Commodity assessment invalid-row status parity (2026-10-24)

- [x] Prevent an assessment with all three required commodity evidence types marked verified from returning `evidence_coverage_complete` when additional malformed rows or unrecognized evidence types are present.
- [x] Expose `unrecognized_evidence_type_count` and retain `invalid_evidence_record_count`; invalid inputs now produce `evidence_invalid_or_incomplete` unless a status conflict takes precedence.
- [x] Add offline regression tests for unknown evidence types and malformed extra rows alongside otherwise complete evidence.
- [x] Updated the pre-existing non-list-input regression expectation to match the stricter `evidence_invalid_or_incomplete` result; fix commit `5773934e0d5937cd1b2fa8e78de41ce1e11db398`.
- [x] All four workflows passed on corrected code/test commit `5773934e0d5937cd1b2fa8e78de41ce1e11db398`: Technical Analysis Tests (run `40110294522`), evidence-ingestion API checks (`40110294507`), screening checks (`40110294532`), and CIN Automated Tests (`40110294558`). The prior run exposed a stale assertion; that expectation was corrected before this passing run.
- **Boundary:** all checks are offline/mocked; no merge or production deployment was performed.

## Strict identifier end-anchor follow-up (2026-10-24)

- [x] Replaced end-of-line anchors with absolute end-of-input anchors in the commodity backing, growth fundamentals, public evidence ingestion, public candle, and derivatives request schemas. This closes the final-newline edge case where a regex end-of-line anchor may match before a trailing newline.
- [x] Added regressions for trailing newlines in commodity/growth symbols and public evidence repository paths; updated OpenAPI pattern assertions for public candles and derivatives.
- [x] All four repository CI workflows passed on code/test revision `ff4baa97e07a8fcc4f93298259ac48466fe8f91a`: screening checks (run `40111015218`), technical-analysis tests (`40111015225`), evidence-ingestion API checks (`40111015262`), and automated tests (`40111015247`).
- **Boundary:** identifier validation only checks request syntax; it does not establish whether a market pair is listed or whether submitted evidence is authentic.

## Portable schema and strict full-string validation correction (2026-10-24)

- [x] Kept OpenAPI patterns in portable regex syntax rather than exposing an engine-specific absolute-end anchor to downstream clients.
- [x] Added explicit `re.fullmatch` validators for commodity/growth/evidence-ingestion body identifiers and repository paths.
- [x] Made public candle validation reject leading/trailing whitespace before normalization; added equivalent pre-provider symbol validation to the derivatives endpoint.
- [x] Added trailing-newline regression tests at request-model and route boundaries.
- [x] All four workflows passed on code/test revision `13ebf4419442e61c6886164ef78536ca3a65bbf1`: screening checks (`40111232668`), technical-analysis tests (`40111232641`), evidence-ingestion API checks (`40111232681`), and automated tests (`40111232706`).
- **Boundary:** the regex/validator checks enforce syntax only; provider pair listing and source authenticity remain separate concerns.


## Assessment-clock CI regression closure (2026-10-24)

- [x] Reviewed the failed screening workflow on PR merge revision `b6ecc336edf4080834090a646e44a6427ddbf4ff`. The commodity assessment path failed because the merge snapshot lacked the validated `current` / `assessment_clock_valid` initialization while normalization referenced those names.
- [x] Confirmed the feature-branch implementation initializes a timezone-aware UTC assessment clock, passes it to each normalized row, and reports clock validity consistently in both summary and evidence rows; regression tests cover valid, naive, and malformed clocks.
- [x] Re-ran CI on corrected code/test revision `d829699ac591e2ef6b430ae274108a844f576eef`; all four workflows concluded success: CIN screening checks (`40106430183`), CIN Automated Tests (`40106430190`), evidence ingestion API checks (`40106430187`), and Technical Analysis Tests (`40106430182`).
- **Boundary:** the failed run is a real CI regression, not a live-provider issue. No merge or production deployment was performed.

## Future-dated assessment evidence age regression follow-up (2026-10-24)

- [x] Added regression assertions that future-dated commodity evidence has no non-negative publication-age value, rather than being reported as age zero.
- [x] Added equivalent growth-fundamentals assertions for null publication age and the explicit `published_at_is_in_the_future` validation error.
- [x] Reviewed the earlier screening workflow failure on revision `a1a9e2bfa7fe1ffb6a006c6cddda0b7a7cd80b41`: the commodity assessment code at that revision referenced the assessment clock before defining it. The current feature-branch file has a shared `_assessment_clock` helper, initializes the clock before normalization, and propagates clock validity to the summary and evidence rows.
- [ ] CI confirmation for current PR head `9124da9a6a38b39bef272d5be66fde57fd20d148` remains pending: the workflow lookup returned no runs for that SHA. Do not treat the historical failed run as a passing check.
- **Boundary:** these are metadata sanity checks, not independent verification of the underlying evidence claims. No merge or production deployment was performed.

## Assessment evidence status enum validation (2026-10-24)

- [x] Tightened both commodity-backing and growth-fundamentals API request models so caller-supplied evidence status must be one of `verified`, `unverified`, `stale`, or `unavailable`; unsupported status strings now fail request validation instead of being silently normalized.
- [x] Added offline regression tests for unsupported status values in both request models.
- **Boundary:** accepted `verified` remains caller-supplied metadata, not CIN's independent verification of evidence claims. This change only makes the public request contract stricter.
- [ ] CI status for the newest request-contract tests must be checked before this batch is marked validated.


## API reliability and release-readiness audit (2026-10-25)

- [x] Re-checked PR #8's current head `dac8f646b20f580be7257a60db03d272253c29f6` and confirmed all four GitHub Actions workflows completed successfully on that exact commit: CIN Automated Tests (run `40123474267`), CIN screening checks (run `40123474281`), CIN Technical Analysis Tests (run `40123474309`), and CIN evidence ingestion API checks (run `40123474227`).
- [x] Audited the current branch's public evidence ingestion and market-candle API boundaries for strict request schemas, allowlist enforcement, provider error sanitization, malformed candle rejection, timestamp representability, and closed-candle-only technical analysis. Existing regression tests cover these offline/mocked cases; passing CI is not a live-provider certification.
- [x] Confirmed the pull request remains Draft and unmerged. The production Render service and its configuration were not changed as part of this audit.
- [ ] Before release: run read-only live smoke checks for production health/readiness and route registration; compare the existing Render deployment with the PR branch; validate Kraken pair-key/quote-currency mappings against actual provider responses; review generated OpenAPI schemas for all public endpoints and confirm documented error responses match runtime behavior.
- [ ] Record the production-only checks and results separately from offline CI. Do not claim live verification until those checks have actually run and their outputs have been inspected.
- **Release decision:** not cleared. Keep PR #8 in Draft until the release gates above are completed. Merging is not authorized by this audit because the `main` Render configuration may automatically deploy.
- **Safety boundary:** CIN remains read-only research, analysis, monitoring and alerting. No trade/order execution, wallet control, private keys, seed phrases, or fund movement. Preserve the ₹0-first approach.


## Kraken fallback parser regression coverage (2026-10-25)

- [x] Added offline tests for Kraken OHLC responses using the alternate `XXBTZUSD` pair key and the `XBTUSDT` pair key, including pair query construction, quote-currency provenance, volume extraction, and normalized candle close-time calculation.
- [x] Added a malformed Kraken response-shape regression test.
- [x] All four workflows passed on test commit `82219630a649f9273fad7e69c880a7b2b2549d2d`: CIN Automated Tests (run `40123716245`), CIN screening checks (`40123716265`), CIN Technical Analysis Tests (`40123716292`), and CIN evidence ingestion API checks (`40123716284`).
- **Boundary:** fixtures are mocked and validate parser behavior only; they do not confirm live Kraken pair availability or exchange response behavior. No merge or production deployment was performed.


## Post-test CI and PR state recheck (2026-10-25)

- [x] Confirmed the implementation-tracker update commit `b96c363a8178a2d1a549361c026d4eab7d25fcbe` also completed all four CI workflows successfully: CIN Automated Tests (run `40123745460`), CIN evidence ingestion API checks (`40123745385`), CIN Technical Analysis Tests (`40123745433`), and CIN screening checks (`40123745435`).
- [x] Reconfirmed PR #8 is open, Draft, and unmerged.
- [ ] Live Kraken pair availability and production health/readiness remain unverified. No production URL was established from repository evidence during this pass; do not guess one. Continue with repository-level OpenAPI/error-contract audit and request the existing deployment URL only if a live smoke test cannot be run from existing authorized configuration.
- **Boundary:** passing CI verifies the repository's offline/mocked checks only. No merge, deployment, account connection, or trade execution was performed.

## Public candle analysis API contract regression tests (2026-10-25)

- [x] Added offline regression coverage that proves a forming candle is excluded from the technical-analysis input while request/use counts and the exclusion count remain explicit.
- [x] Added offline regression coverage that returns HTTP 422 when fewer than five completed candles are available for analysis.
- [x] Wired `tests/test_cin_public_market_candles.py` into `.github/workflows/cin-ci.yml`; before this change, the new suite was not explicitly executed by the four workflows.
- [x] All four workflows passed on code/test/CI commit `e64e9bd5a8ebba9cb8039d94bba5272063ebc156`: CIN Automated Tests (run `40124087516`), CIN screening checks (`40124087510`), CIN Technical Analysis Tests (`40124087492`), and CIN evidence ingestion API checks (`40124087553`).
- [x] Inspected the automated workflow job: the newly added `Run public candle API contract regression tests` step completed successfully.
- **Boundary:** these tests mock the provider loader and verify API behavior only. They do not validate live exchange data or the deployed Render revision.

## Public candle API documentation and freshness contract (2026-10-25)

- [x] Corrected `docs/CIN_PUBLIC_MARKET_CANDLES.md` to describe Binance as primary and Kraken fallback only after HTTP 451, controlled provider errors, completed-candle analysis, provenance, and freshness metadata.
- [x] Added a regression test confirming `/market-candles` marks all-forming rows as forming and reports that no completed candle is available.
- [x] All four CI workflows passed on code/test commit `ed28e5f877847f5b0f1ae3eea17c46dc14b8fc6e`: CIN Automated Tests (`40124689165`), CIN screening checks (`40124689259`), CIN Technical Analysis Tests (`40124689273`), and CIN evidence ingestion API checks (`40124689601`). The public candle test step passed within CIN Automated Tests.
- **Boundary:** all checks use mocked/offline provider responses. No live exchange or deployed API health was verified.

## Caller-supplied technical-analysis request schema (2026-10-25)

- [x] Restricted `timeframe` to alphanumeric characters, dots, underscores, and hyphens; whitespace and control characters now fail Pydantic request validation.
- [x] Added request-model regression tests for valid timeframe, whitespace/control-character rejection, default timeframe, and forbidden extra fields.
- [x] Added an explicit CI step to run `tests/test_cin_technical_analysis.py` from the repository root so the API request schema tests are actually executed.
- [x] All four workflows passed on code/test/CI commit `d8571d3010dca26a0058f07676aaaa637d6fadc1`: CIN Automated Tests (`40124885343`), CIN Technical Analysis Tests (`40124885412`), CIN screening checks (`40124885344`), and CIN evidence ingestion API checks (`40124885349`). Both new technical-analysis request contract tests and existing public-candle contract tests passed in the automated suite.
- **Boundary:** offline tests only; no live provider or production endpoint was contacted. PR remains open, Draft, and unmerged.

## Derivatives order-book data-quality transparency (2026-10-25)

- [x] Added explicit counts for malformed, non-finite, or non-positive order-book levels rejected from bid/ask calculations; counts are returned as `bid_levels_rejected` and `ask_levels_rejected` within `order_book`.
- [x] Added a data-quality limitation explaining that rejected levels are excluded and counted, so partially malformed depth does not appear fully clean.
- [x] Added regressions for mixed valid/invalid depth levels and empty open-interest history; history-derived values and timestamps remain null when no history is available.
- [x] All four workflows passed on code/test commit `1596de175210a952c3e6f74da9b8b6111f754e1e`: CIN Automated Tests (run `40125108093`), CIN screening checks (run `40125108087`), CIN Technical Analysis Tests (run `40125108135`), and CIN evidence ingestion API checks (run `40125108083`). The derivatives regression step passed in the automated workflow.
- **Boundary:** tests use mocked provider payloads; they do not establish live Binance availability or production endpoint health. PR #8 remains Draft and unmerged.

## Derivatives timestamp freshness classification (2026-10-25)

- [x] Added timestamp-quality metadata for open interest, mark-price/funding, and latest open-interest history: provider timestamp, age in seconds, status, and freshness threshold.
- [x] Mark current open-interest and premium-index timestamps stale after 15 minutes; mark 4-hour open-interest history stale after 8 hours; classify timestamps more than 60 seconds ahead as future-dated.
- [x] Missing history is classified as unavailable rather than invalid, preserving the prior contract that empty history yields null history-derived values.
- [x] Added regression tests for fresh, stale, future-dated, and unavailable timestamp states, plus an integration-style snapshot test that verifies warning fields.
- [x] All four workflows passed on code/test commit `6fd11d8e90d1b0340574ebec97bed9ab3a6edc54`: CIN Automated Tests (run `40125347836`), CIN screening checks (`40125347837`), CIN Technical Analysis Tests (`40125347825`), and CIN evidence ingestion API checks (`40125347822`). The derivatives regression step passed in CIN Automated Tests.
- **Boundary:** fixed-time and mocked-provider tests only; no live exchange or production endpoint was contacted. PR #8 remains Draft and unmerged.

## Public news provider timestamp semantics (2026-10-25)

- [x] Corrected the news response contract to expose GDELT `seendate` under `provider_seen_at`, `provider_seen_at_utc`, and `provider_seen_at_validation_status`; legacy `published_at*` fields remain for compatibility and are documented as aliases, not verified publication times.
- [x] Added detection for provider timestamps more than 60 seconds in the future, preserving the normalized value while returning `future_dated`.
- [x] Added deterministic regression coverage for future timestamps and assertions that the new fields and compatibility aliases agree.
- [ ] Await all four CI workflows on the latest documentation/tracker head before marking this milestone fully verified.
- **Boundary:** offline/mocked tests only; no live GDELT request or production deployment check performed. PR #8 remains Draft and unmerged.


## Cross-provider evidence consistency — news timestamp quality (2026-10-25)

- [x] Added aggregate counts for GDELT provider seen-time states: valid, missing, invalid timezone, invalid, and future-dated.
- [x] Explicitly states that the headline sentiment aggregate still includes all accepted headlines regardless of timestamp status; timestamp quality must be reviewed before time-sensitive use.
- [x] Added offline regression coverage for mixed valid, missing, and future-dated provider timestamps.
- [ ] Verify all CI workflows on the latest head before treating the milestone as complete.
- **Boundary:** counts describe provider seen/indexing time, not verified original publication time. Offline tests do not verify live GDELT or production behavior. PR #8 remains Draft and unmerged.

## Cross-provider evidence consistency — candle duplicate conflicts (2026-10-25)

- [x] Public candle normalization now collapses exact duplicate rows sharing an open timestamp but rejects conflicting OHLCV/close-time values for that timestamp rather than silently using the last row.
- [x] Added offline regression tests for identical duplicates and conflicting duplicates; documented the rule and its limits.
- [ ] Verify all four CI workflows on the latest head before marking this milestone verified.
- **Boundary:** this validates duplicate consistency within one provider response. It does not compare Binance and Kraken simultaneously or verify live exchange data. PR #8 remains Draft and unmerged.

- **Regression adjustment:** the existing market-candle safety test had intentionally used conflicting same-timestamp rows and expected silent last-row-wins behavior. Updated it to test exact duplicate collapse; the new dedicated test asserts conflicting evidence is rejected. The initial automated workflow failure on the intermediate docs commit exposed this stale expectation; latest-head CI is the verification gate.

## Derivatives evidence completeness — unavailable history (2026-10-25)

- [x] Empty open-interest history is now surfaced as a freshness warning rather than leaving the snapshot marked `ok`.
- [x] Added `data_quality.analysis_eligibility` and an explanatory reason: `not_recommended` when timestamp evidence is stale, future-dated, invalid, or unavailable; the endpoint remains readable for inspection.
- [x] Updated regression coverage and derivatives endpoint documentation.
- [ ] Verify all CI workflows on latest head before marking the milestone verified.
- **Boundary:** this is a consumer-facing quality warning, not a live-provider guarantee. Missing history-derived metrics remain null. PR #8 remains Draft and unmerged; no deployment performed.

## Screening cache and provider timestamp consistency — 2026-10-25

- [x] Preserve provider timestamp status and age separately from the effective `stale_cache` state.
- [x] Regression test verifies stale-cache results remain ineligible even when the provider's own `last_updated` timestamp appears fresh.
- [x] Documented the distinction between response-level cache age, provider timestamp age, and analysis eligibility.
- [ ] Verify all latest-head CI workflows before marking this milestone fully verified.
- **Boundary:** this is offline regression coverage; it does not verify live CoinGecko/CoinPaprika behavior or deployed service health. PR #8 remains Draft and unmerged.

## Screening numeric evidence and arithmetic safety — 2026-10-25

- [x] Negative market-cap, volume, FDV, and supply magnitudes are treated as missing evidence.
- [x] Added finite-result guards for volume/market-cap, FDV-gap, and circulating-supply ratios.
- [x] Added offline regression coverage for negative metrics and extreme finite values that overflow ratios.
- [x] Documented that non-finite derived ratios are returned as null and do not earn points.
- [ ] Verify all CI workflows on the final commit before marking the milestone fully verified.
- **Boundary:** no live provider or deployment health is inferred from offline tests. PR #8 remains Draft and unmerged.

## Screening identity and ranking determinism — 2026-10-25

- [x] Discard rows without a non-empty provider asset ID before scoring.
- [x] Collapse duplicate IDs case-insensitively, preserving the first provider row deterministically.
- [x] Expose input, invalid-identity, duplicate-ID, and accepted-identity counts in response `data_quality` metadata.
- [x] Add offline regression tests and document the identity policy and its limitations.
- [x] Verify all four CI workflows on final commit `fa8d0c443beb9d81f5bc5b1d539b310363026cc3`: CIN Automated Tests, CIN screening checks, CIN Technical Analysis Tests, and CIN evidence ingestion API checks all completed successfully (runs `40128798174`, `40128797810`, `40128797811`, `40128797876`). These are offline/mocked checks only.
- **Boundary:** distinct provider IDs may still represent the same real-world asset; no canonical cross-provider identity mapping is claimed. PR #8 remains Draft and unmerged.


## API contract documentation alignment — 2026-10-25

- [x] Corrected public candle documentation to distinguish FastAPI request-schema HTTP 422 responses from explicit semantic HTTP 400 validation and insufficient completed-candle HTTP 422 responses.
- [x] Corrected derivatives documentation: unavailable open-interest-history timestamps are included in freshness warnings, so empty history yields `freshness_status: warning` and `analysis_eligibility: not_recommended`; history-derived values remain null.
- [x] Confirmed all four CI workflows passed on the candle-contract documentation commit `da718a35a2bd3bd1829024d201d85198ed3b6588`: Automated Tests (`40141730746`), screening checks (`40141730799`), Technical Analysis Tests (`40141730768`), and evidence ingestion API checks (`40141730771`). The subsequent derivatives-doc and tracker commits have no reported workflow runs; this does **not** certify the final documentation head.
- **Boundary:** documentation-only edits; no runtime code, production configuration, or deployment changed. CI and live provider behavior remain unverified for these latest documentation commits.


## Public candle OpenAPI contract — 2026-10-25

- [x] Added explicit OpenAPI response documentation for HTTP 400 semantic validation, HTTP 422 request-schema/insufficient-closed-candle validation, HTTP 502 provider/analysis failures, and HTTP 503 temporary provider failures on both public candle routes.
- [x] Added regression tests for the generated OpenAPI response status set and actual HTTP behavior: malformed symbol request schema returns 422; unsupported interval semantic validation returns 400.
- [x] CI exposed an optional test-client dependency mismatch (`starlette.testclient` requires `httpx2`, which is not installed by the existing workflows). Reworked the regression test to validate OpenAPI request constraints and handler semantic validation without introducing that dependency. New verification head: `ce294dfd1bcb3abdc40e0f9bdd2d88b2b87dc066`; all four workflows passed: Automated Tests (`40141916209`), screening checks (`40141916234`), Technical Analysis Tests (`40141916212`), and evidence ingestion API checks (`40141916215`). The tracker-only follow-up commit does not rerun these workflows.
- **Boundary:** local execution is not claimed; CI results were not available when this tracker entry was written. No live provider smoke test, production configuration change, or deployment was performed. PR #8 remains Draft and unmerged.


### Public candle API error-contract clarification (2026-10-25)
- Corrected OpenAPI 400 descriptions: they no longer imply all invalid symbols return 400. Query-schema failures (including symbol length/pattern and limit bounds) are represented as 422 by FastAPI; unsupported intervals and semantic validation handled by the route return 400.
- Added regression assertions for the documented 400 semantics and presence of the 422 response description on both candle endpoints.
- Code commit: `4536d9616a7be95c155fa4c8ee51f707ab39ba36`; regression test commit: `f2aa7c40fa840dd7a1f303b31f9206d2210faa4e`.
- CI status for this latest test commit has not yet been confirmed. No live-provider smoke test or deployment is claimed.


### Public candle provider response-size hardening (2026-10-25)
- The shared Binance/Kraken JSON request helper now reads at most 2,000,001 bytes and rejects bodies above the 2 MB cap before UTF-8 decoding or JSON parsing.
- Added regression tests for a valid bounded JSON response and an oversized body, including an assertion that the read is capped at limit + 1 byte.
- Runtime code commit: `4ced9fb2743ba51ee2449b37f7b4ae659d5a8b6e`; test commit: `320f19829bf4e105197769b83342e5c40d60ef26`.
- CI on the latest head is pending; no live-provider behavior or deployment is claimed.


### Kraken fallback pair-identity validation (2026-10-25)
- The Kraken OHLC fallback now requires exactly one returned pair key and validates its normalized base/quote identity against the requested symbol before accepting candles.
- This prevents a malformed or unexpected provider result from being mislabeled as the requested asset pair.
- Added offline regression tests for mismatched pair identity and ambiguous multi-pair responses; existing BTC/USD and BTC/USDT response-key cases remain covered.
- Latest code commit: `f32a651380958c40e7adfdfc109e318e8891707f`; test commit: `91b4d8cf82cc98af57e59b2b770c43aacbbea95f`. CI validation on the updated head is pending.
- Boundary: mocked tests do not verify live Kraken pair aliases or quote-currency support. PR #8 remains Draft and unmerged.

- Follow-up regression coverage: explicitly rejects a Kraken BTC/USD result when the requested symbol is BTC/USDT, preventing quote-currency substitution even when the base asset matches (test commit `7a821b28c3e4ba95681df235c82ccd73f1bfeb94`). Latest-head CI is pending.

### Requested candle-count enforcement (2026-10-25)
- Binance candle parsing now rejects a provider response containing more valid candles than the requested `limit`, preserving the endpoint's response-count contract even if a provider returns unexpected data.
- Added an offline regression test for an over-limit Binance response. Existing normal response and Kraken fallback behavior remains covered.
- Code commit: `918a2021eea6d2da0afeb6d9af21d6346d4d6510`; test commit: `03824743898b814b818e6fcdeaadf5e7e48285f8`. CI validation for the latest tracker commit is pending.

### Provider timestamp type hardening (2026-10-25)
- Binance candle parsing now skips rows whose open or close timestamp is a JSON boolean; Kraken parsing likewise skips boolean open timestamps. Python treats booleans as integers, so coercion could otherwise turn malformed provider data into plausible timestamps.
- Added offline regression tests for both providers.
- Code commit: `707f1071f533082db98316e70810409a0a1a34e4`; test commit: `54389c9e979b723298ca9caa4c58bc9cb12fead4`. CI validation for the latest tracker commit is pending.

### Strict provider timestamp parsing (2026-10-25)
- Tightened timestamp parsing beyond boolean rejection: Binance open/close timestamps must be integer JSON values; Kraken open timestamps must be numeric, finite, and whole epoch seconds. String-coercible and fractional timestamp values are skipped instead of silently coerced or truncated.
- Added offline regression coverage for string timestamps from Binance and string/fractional timestamps from Kraken.
- Code commit: `7a7e10ba8fd65abdb2d04a5dcd77d53370b03c42`; test commit: `5a39471cb6abec9ba6fd84423f5cf20a45b2ba9e`. The configured four-workflow CI suite subsequently passed on documentation checkpoint `1b847b843c14e0929f9ec972fbc36af14b70a356`; this is offline CI evidence, not live-provider validation.

### Provider OHLCV boolean-value hardening (2026-10-25)
- Binance and Kraken parsing now rejects JSON booleans in price and volume fields before numeric conversion; Python would otherwise convert `true`/`false` into 1.0/0.0 and could let malformed provider evidence appear numeric.
- Added offline regression tests for both providers.
- Code commit: `0424acd46d43ecb4e6bb3028694d82e207c9f61f`; test commit: `e24a28f6bfb4b095e951a78c36809e6d8ee6530d`. CI validation for latest tracker commit is pending.

### Kraken limit-after-validation handling (2026-10-25)
- Kraken candle rows are now validated and cleaned before applying the requested result limit. Malformed trailing rows no longer displace earlier valid candles from the response window.
- Added offline regression coverage with six valid rows followed by a malformed row and a requested limit of five.
- Code commit: `93235086ed413a411ac7ce5627f5b0a1afdce703`; test commit: `ad8222b7e2b4b178b2d4c86e405402cf3ec11a38`. CI validation for the latest tracker commit is pending.


## Master roadmap reference (2026-10-25)

- Created `docs/CIN_MASTER_ROADMAP.md` as the numbered delivery baseline: **7 stages / 35 steps**.
- It distinguishes implemented/offline-tested work from partial acceptance work, pending capabilities, and release-blocked steps.
- This count is a working baseline, not a guarantee that no future requirements will be added. Do not calculate a single completion percentage from mixed-status steps.
- The roadmap creation commit is `9f42395b1775cd5bd1add8f9dd4a8afa275b2fa8`. The documentation milestone was subsequently verified by four successful workflows on `1b847b843c14e0929f9ec972fbc36af14b70a356`.


## Latest CI verification — 2026-10-25

- Verified all four configured workflows completed successfully on commit `1b847b843c14e0929f9ec972fbc36af14b70a356`:
  - CIN Automated Tests — run `40142830679`
  - CIN screening checks — run `40142830668`
  - CIN Technical Analysis Tests — run `40142830721`
  - CIN evidence ingestion API checks — run `40142830681`
- This verifies CI at the documentation/roadmap checkpoint. It does not constitute a live-provider smoke test or production deployment validation.
- The prior provider-hardening entries above were marked pending at the time they were written; the successful workflow runs now confirm the configured automated CI suite passed on a later head containing those changes.


## Market-candle acceptance boundary (2026-10-25)

- Offline tests cover malformed OHLCV values, boolean coercion hazards, timestamp representation, duplicate/conflicting open timestamps, provider pair identity, fallback limit handling, forming-candle exclusion from technical analysis, freshness metadata, and sanitized provider failures.
- The four configured CI workflows passed on checkpoint `1b847b843c14e0929f9ec972fbc36af14b70a356`.
- Still not established: live exchange responses, real-world interval-boundary behavior for all Binance intervals, provider rate-limit behavior under live conditions, or deployed service health.
- Do not describe candle interval alignment as fully validated until an explicit acceptance test covers fixed intervals, weekly boundaries, and the variable-length monthly interval without assuming every month is 31 days.
- Next safe repository task: add a deterministic interval-boundary validation matrix before changing provider acceptance logic; do not perform live network checks in CI or add trading functionality.


## Latest-head CI verification (2026-10-25)

All four configured workflows completed successfully on commit `2c1f816d59bc4fa6aa1c31ce2ee01228cd46f29b`:
- CIN Automated Tests — run [40143004602](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/40143004602)
- CIN screening checks — run [40143004579](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/40143004579)
- CIN Technical Analysis Tests — run [40143004612](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/40143004612)
- CIN evidence ingestion API checks — run [40143004608](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/40143004608)

This checkpoint validates configured offline automation only. It does not establish live exchange availability, interval alignment for every timeframe, rate-limit resilience under live conditions, or deployed service health. In particular, monthly candles must use calendar-month boundaries rather than the existing approximate 31-day duration when validating boundaries or calculating interval-derived freshness thresholds.


## Monthly candle freshness correction (2026-10-25)

- Replaced the fixed 31-day monthly duration in freshness threshold calculation with calendar-month duration derived from the latest closed candle open timestamp; leap years and year rollover are covered.
- Added deterministic tests for 28-, 29-, 30-, and 31-day months and the monthly freshness threshold.
- Code commit: `5259bc9500068d577cba6bc617b9083ae92fdbc3`; test commit: `b4d55897b08dc788e848b9273e4277dc31550702`.
- CI for the new code/test head is pending. This does not yet validate candle open-time alignment, close-time consistency, live provider behavior, or deployed service health.

## Candle boundary validation increment (2026-10-25)

- Added `_candle_time_consistent` and applied it to Binance candle rows: validates close-time duration, weekly Monday UTC anchoring, and calendar-month open/close boundaries.
- Added regression tests for fixed-interval close-time mismatch and monthly leap-year/common-year/month-end boundaries.
- Fixed-interval epoch alignment is deliberately not assumed without provider-specific evidence; 3-day anchoring remains provider-specific. Kraken integration still requires a separate compatibility pass before enforcing the helper there.
- Code commits: `56b9578bba9df3b77168acf7051445ec924bfb15`, `0cb4e6efb60f4228142ceca005279afca54f3f39`; tests: `46e14b24f6c1ad98bb567bb4967242b41dd29f73`.
- CI for this latest code/test head is pending. Live-provider and deployment health remain unverified.

## Future-dated candle guard (2026-10-25)

- `_candle_time_consistent` now rejects candle open timestamps more than 60 seconds ahead of current UTC time; the one-minute tolerance is an explicit clock-skew allowance.
- Added deterministic tests for rejection beyond the tolerance and acceptance at the tolerance boundary.
- Code: `8b7e415d0f910078731ee1c68762d85ede6bf509`; tests: `23da189d12018e73b114fba18a58c5a8c9ad857b`.
- Latest-head CI is pending. Live-provider and deployment checks remain outstanding.

- Follow-up integration regression: Binance parser now has an end-to-end test proving a materially future-dated candle is filtered while a valid candle remains. Test commit: `d6b4797b57ad161b1632884f26e124246fb37a15`; CI pending.
- CI caught a regression-test-only issue: the new end-to-end test referenced `datetime` without importing it. Fixed in `d7b6550dd2a1bc23d0a8de6055598c85cd5d976b`; rerun is pending. The application logic was not implicated by this failure.

- Follow-up CI found the import fix had been inserted at a nested `import asyncio` site, causing an `IndentationError`. Moved `datetime`/`timezone` to the module-level imports in `cdd4e28c4ad1d70e189cea7350cede5ea91e1c8b`. Latest rerun must confirm collection and tests pass.

## Interval-boundary matrix and provider-doc review (2026-10-25)

- Official Binance Spot documentation identifies kline open and close timestamps, lists supported intervals including 3d, 1w, and 1M, and notes that interval interpretation can depend on the optional timeZone parameter. This client does not set timeZone, so its REST requests use the documented UTC default. Reference: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
- Binance stream documentation describes weekly/monthly interval labels and UTC open/close timestamps; this supports testing weekly Monday UTC and calendar-month boundaries, but does not justify inventing an epoch-modulo anchor for 3-day candles. Reference: https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md
- Expanded deterministic tests for weekly Monday-midnight UTC acceptance/rejection and 3-day duration validation without an assumed epoch anchor. Test commit: 796518581664dfb8fc134a797a014c08b3ab6a7f.
- Latest-head CI for the current code and test changes must pass before this matrix is counted as verified. Kraken boundary enforcement remains deferred; offline tests do not establish live-provider behavior.


## Monthly freshness disclosure correction (2026-10-25)

- Corrected stale API limitation text on both `/market-candles` and `/technical-analysis/market`: monthly freshness duration is calendar-aware, not a fixed 31-day approximation.
- Added an offline regression test asserting both endpoint limitation lists match the implemented calendar-month duration and no longer claim a 31-day approximation.
- Code commit: `ac2982945c8efcd4ce53c34fa20046b47d0e9d70`; test commit: `1bfa6145a6b740c87f7538aa985a451b1964c987`.
- CI for the latest branch head must pass before this correction is counted as verified. This is a documentation/contract accuracy fix; it does not establish live provider or deployment health.


## Kraken forming-candle compatibility regression (2026-10-25)

- Kraken's official Spot REST OHLC docs state that the last OHLC array entry is the current, not-yet-committed timeframe and is always present. Source: https://docs.kraken.com/api-reference/market-data/get-ohlc-data
- Added an offline regression test that supplies one completed hourly candle and one current-hour candle, then verifies the fallback preserves both and derives the current candle's close boundary. This protects the provider contract while technical-analysis endpoints separately exclude candles not yet closed.
- Test commit: `43de485f250079dc0d8af7ecbabb536fef249b7a`.
- This does not enable stricter Kraken boundary enforcement or establish live exchange health. Verify all CI workflows on the latest branch head before marking the test as passed.


## Kraken pair-identity negative tests (2026-10-25)

- Added parameterized offline regression coverage proving that a Kraken response for a different base asset (ETH/USD when BTC/USD was requested) or a different quote (BTC/USDT when BTC/USD was requested) is rejected instead of being exposed as the requested market.
- This tests the existing fail-closed pair validation; production behavior is unchanged.
- Test commit: `753031ec49d61a9a161cf3b1c0223068fb5bc5e6`.
- Awaiting all four GitHub Actions workflows on the latest branch head.


## Malformed Kraken payload regression coverage (2026-10-25)

- Added offline tests for non-object payloads, non-object result containers, missing pair rows, non-list candle rows, and provider-declared pair errors.
- Each malformed/failing fallback response must surface as a sanitized HTTP 503 through CIN's provider loader, without leaking parser details or payload contents.
- Test commit: `1840cabb0cf17eba0c98ef5b41d501051becdf23`.
- Awaiting all four CI workflows on the latest branch head.


## Malformed Kraken error-field regression coverage (2026-10-25)

- Extended the controlled-fallback regression matrix to include malformed `error` fields (integer, string, and object-list entries), alongside malformed result containers and candle rows.
- Expected outcome remains a sanitized HTTP 503; raw provider payloads and parser details must not appear in the API response.
- Test commit: `f52a2ed1a7b4e6062e2561d04079894b0f3dd26d`.
- CI verification pending on the latest tracker commit.


## Kraken error-field schema validation (2026-10-25)

- Kraken OHLC responses must now contain an `error` field represented as a list of strings, matching the documented response shape.
- Missing, null, string, object, integer, or non-string list entries are rejected as malformed rather than being accidentally accepted when falsy or raising incidental type errors.
- Added fallback API regression cases to assert malformed payloads remain controlled and sanitized.
- Code commit: `5cea6dc6d143b265439f36c1edc01ecec61e7cdf`.
- Test commit: `697501bc2e257ea8489bb9230b8aafbd68e4391f`.
- CI verification pending on the latest tracker commit.


## Kraken pair-key type validation (2026-10-25)

- The parser now explicitly rejects non-string trading-pair keys before normalization, producing a clear validation failure rather than relying on an incidental attribute error.
- Added a malformed result-key regression case to the controlled fallback test matrix.
- Code commit: `2ff41eb63615b24eff3402e00b4635405c029191`.
- Test commit: `3761aa86b59388c3ac2f2c6956cd55fbe65e34bb`.
- CI verification pending on the latest tracker commit.


## Provider-error detail sanitization assertions (2026-10-25)

- Strengthened malformed Kraken payload tests to explicitly assert that provider error codes/messages and malformed-field marker strings are not returned to API clients.
- This locks down the public API contract: fallback failure is reported as a controlled 503 without leaking provider payload internals.
- Test commit: `b5ac4b39b0ac52d4dd0836e090bee87344510887`.
- CI verification pending on the latest tracker commit.


## Unsupported Kraken pair-identifier regression cases (2026-10-25)

- Added controlled-fallback cases for a result key using an unsupported quote suffix and for a syntactically shaped but mismatched USD pair identifier.
- These cases ensure pair identity validation rejects unsupported or unexpected provider keys before candle data can be returned.
- Test commit: `aa0834be6e6788277587429365c4f4ca8b8aadfb`.
- CI verification pending on the latest tracker commit.


## Oversized Kraken timestamp regression case (2026-10-25)

- Added a malformed provider payload with an integer timestamp far beyond the representable epoch range.
- This verifies that extreme timestamp values are contained by the controlled fallback error path and cannot escape as an unhandled parser failure or expose provider details.
- Test commit: `48f589a64fd7956d67e020ee2afed2464add915c`.
- CI verification pending on the latest tracker commit.


## Kraken unrepresentably large integer timestamp guard (2026-10-25)

- Hardened timestamp validation so an integer too large to convert to a float is rejected as a malformed row rather than escaping the parser's numeric checks.
- Expanded the regression payload to use a 1,001-digit timestamp, covering the overflow path directly.
- Code commit: `c3b51db8fdd5d7cc8a1e9bc567b1a97854ff1905`.
- Test commit: `1cd3a8a32f0da6ca4ace87b25c08fe39dd6d9954`.
- CI verification pending on the latest tracker commit.


## Kraken floating-point timestamp overflow case (2026-10-25)

- Extended the oversized-timestamp regression payload to include both a 1,001-digit integer and a finite `1e308` float whose millisecond conversion overflows.
- Confirms both integer-to-float validation and float-to-millisecond conversion are contained as invalid rows.
- Test commit: `8a7b4e4565f25c3f51b142859643953a165b8448`.
- CI verification pending on the latest tracker commit.


## Public provider response-size limit regression (2026-10-25)

- Added an offline test proving the JSON transport reads no more than the configured response cap plus one byte and rejects an oversized provider body before JSON decoding.
- This protects the public market-data path against unexpectedly large responses and unbounded buffering.
- Test commit: `6d9b0790f455fca840c890ecd7c9255699e6ed59`.
- CI verification pending on the latest tracker commit.


## Provider response-size boundary test (2026-10-25)

- Added a boundary regression proving a valid JSON body exactly at the configured 2,000,000-byte limit is accepted, complementing the oversized-body rejection test.
- Together, the tests cover both sides of the transport's size boundary without external network access.
- Test commit: `a322c7770703919281d407487090652081be7846`.
- CI verification pending on the latest tracker commit.


## Oversized provider body API error contract (2026-10-25)

- Added an end-to-end offline regression for an oversized Binance-style provider body.
- Confirms the transport rejection is translated into the established sanitized HTTP 502 response; the internal size-limit exception is not exposed to API clients.
- Test commit: `0c69500179e763126d3d41e10d3a4fe4fd435392`.
- CI verification pending on the latest tracker commit.
