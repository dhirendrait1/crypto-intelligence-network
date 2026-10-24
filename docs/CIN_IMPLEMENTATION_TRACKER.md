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
| Public evidence ingestion | Allowlisted public GitHub metadata for three Ethereum-related repositories; repository identity type-checked; counters must be non-negative integers (booleans rejected); timestamps must be ISO-formatted with explicit timezone; missing optional fields are surfaced as `metadata_partial`; malformed payloads raise controlled source errors; offline regression tests | Partial / offline-tested | Add API-level malformed-payload regression coverage; freshness policy implemented: fresh ≤7 days, stale >7 days, unknown when timestamps are unavailable; timestamps >5 minutes in the future are rejected; not a general news/social connector |
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
- [x] Verify the new regression tests and all four repository workflows on commit `7e26219dc57b752255f6e58e8aefdf1f28e749e1`; all four workflows passed. These are offline/mocked tests, not live provider validation.
- **Boundary:** these checks validate supplied metadata only. CIN still does not fetch source documents or independently certify reserve, custody, solvency, or redemption claims.


## Growth fundamentals evidence validation (2026-10-24)

- [x] Audit the current assessment contract and confirm the coverage score measures submitted evidence metadata, not project quality or investment merit.
- [x] Require absolute HTTP(S) URLs with a parsed hostname rather than accepting a scheme-prefix string.
- [x] Add regression tests for scheme-only URLs, URLs without a hostname, and valid HTTP URLs.
- [x] Verify all four GitHub Actions workflows on commit `31f8ad04051e15ef028d85ee58f0dd79e2826b9f`; all passed. Results are offline tests only.
- [ ] Reject future publication timestamps for supplied `verified` records; this remains an identified gap and is not claimed as fixed.
- [ ] Add evidence conflict resolution and independent source retrieval; the endpoint currently assesses caller-supplied metadata only.
