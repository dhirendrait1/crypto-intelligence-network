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
| Public news search / headline sentiment | `cin_public_news_sentiment_api.py`, `docs/CIN_PUBLIC_NEWS_SENTIMENT.md`, mocked GDELT response/failure tests; router added to scaffold patch and CI | Partial / offline-tested | Live GDELT validation, improved sentiment methodology, source quality and article-time freshness monitoring |
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
