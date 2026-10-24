# CIN Architecture & Completion Register

Last reviewed: 2026-10-24  
Repository: `dhirendrait1/crypto-intelligence-network`  
Status: working register; not a release certification.

## Purpose and safety boundary

Crypto Intelligence Network (CIN) is a read-only crypto research, intelligence, forecasting, monitoring, and alerting system. It does not place orders, execute trades, control wallets, move funds, or handle private keys/seed phrases. Public order-book data may be analyzed, but order placement is out of scope.

This register distinguishes four states that must not be conflated:

- **Designed** — the requirement or interface is documented.
- **Implemented** — corresponding source code exists.
- **Tested** — behavior has passing automated tests or documented validation.
- **Deployed** — the exact code is running in the target environment and has been verified there.

A module may hold more than one state. “Router registered” alone is not proof of complete implementation or reliable live data.

## Architecture layers

1. **Public data adapters** — exchange candle endpoints and allowlisted public evidence sources.
2. **Normalization and provenance** — canonical symbols/timeframes, provider/pair identifiers, quote currency, timestamps, freshness and data-quality limitations.
3. **Research engines** — screening, deterministic technical analysis, fundamentals and evidence assessments.
4. **Intelligence outputs** — explainable findings, scenarios, risk/reward context, confidence and explicit missing-data labels.
5. **Monitoring and delivery** — scheduled refresh, alert rules, notifications, historical signal/forecast tracking and dashboard/API clients.
6. **Governance and operations** — offline regression tests, read-only safety, error handling, observability, release checks and cost controls.

Layers 4–6 require further source-level and end-to-end verification; the list is the target architecture, not a claim that every layer is complete.

## Verified source and router inventory

The deployment patch `patch_cin_metadata_fixed.py` names the following source modules and registers the listed read-only router families in the FastAPI application.

| Component | Source module(s) | Evidence/status |
|---|---|---|
| Public market data | `market_data_step1.py` | Read-only CoinGecko adapter now rejects non-finite/negative prices, omits invalid optional metrics with warnings, exposes per-row freshness from provider timestamps (fresh ≤15 minutes, stale >15 minutes, unknown for missing/invalid/future timestamps), and maps unexpected status to controlled invalid-response handling; offline regression tests added; no live-provider validation claimed |
| Coin screening | `coin_screening_step2.py` | Named in deployment patch; full behavior audit pending |
| Commodity backing assessment | `commodity_backing_assessment.py`, `commodity_backing_api.py` | Named in deployment patch; full behavior audit pending |
| Growth fundamentals | `growth_fundamentals_assessment.py`, `growth_fundamentals_api.py` | Named in deployment patch; full behavior audit pending |
| Public evidence ingestion | `cin_evidence_ingestion.py`, `cin_evidence_ingestion_api.py` | Named in deployment patch; full source and allowlist audit pending |
| Caller-supplied OHLC analysis | `cin_technical_analysis.py`, `cin_technical_analysis_api.py` | Named in deployment patch; prior offline technical-analysis checks passed; full feature audit pending |
| Exchange-backed candle data and analysis | `cin_public_market_candles_api.py` | Closed-candle, volume and completed-candle freshness behavior covered by offline regression tests; no live-provider validation claimed |
| Read-only derivatives and order-book snapshot | `cin_derivatives_market_data_api.py` | Public Binance USDⓈ-M endpoints for open interest, funding, mark/index price, latest two 4h OI aggregates, best bid/ask, spread, per-side valid levels and approximate notional imbalance; order-book retrieval time included; offline tests cover invalid crossed books |
| Public news search and headline sentiment | `cin_public_news_sentiment_api.py` | GDELT public article search, URL deduplication, article timestamps, transparent low-confidence keyword sentiment; offline tests; explicitly not social-platform sentiment |
| API health/readiness | FastAPI app endpoints | Live `/health` and `/ready` returned healthy/ready in earlier checks; recheck after any future release |

The patch copies the source modules into `cin/app` during the build. The source inventory therefore needs to be audited together with the generated scaffold and patch process.

## Market-data acceptance criteria

- Provider name and endpoint are explicit.
- Actual provider pair key and quote currency are reported when reliably known.
- Every candle reports UTC open/close timestamps and closed/forming state.
- Market-candle and market-analysis responses report the latest completed candle's age and a transparent stale-data warning threshold (twice the requested interval; monthly intervals use a 31-day approximation). No-completed-candle states are explicit.
- Analysis excludes forming candles and reports requested, used and excluded counts.
- Unsupported fallback intervals/pairs fail clearly; no fabricated fallback data.
- Missing, stale, partial or unverified inputs are surfaced instead of silently guessed.
- When volume is present, analysis reports latest volume, the mean of up to 20 preceding candles, and relative volume against that baseline; if volume is absent, outputs explicitly mark it `not_supplied`. These are descriptive metrics, not standalone buy/sell signals.
- Swing highs/lows are described as reference levels, not verified resting liquidity.
- Tests use mocks/offline fixtures and never place orders or access private accounts.

## Current verified test evidence

Previously recorded CI on the market-data validation branch:
- Scaffold tests: 11 passed.
- Market-data regression tests: 13 passed.
- Technical-analysis offline checks: passed.
- Screening and evidence-ingestion offline checks: passed.

On commit `60a5fa6e87b77edc23240a1863a5aae115613149`, all four GitHub Actions workflows completed successfully: CIN Automated Tests, CIN screening checks, CIN Technical Analysis Tests, and CIN evidence ingestion API checks. The scaffold CI extracts the same scaffold archive used by the deployment patch, registers the read-only derivatives and public-news routers, and runs their offline regression tests. These are mocked/offline results and do not certify live exchange/news availability, provider freshness, or production behavior.

## Work still requiring verification or implementation

The following are not marked complete until code and evidence are inspected:

- Full source review of screening and assessment algorithms, including inputs, scoring rationale and missing-data behavior.
- Evidence ingestion: repository allowlist, timeout bounds, source attribution, malformed JSON identity handling, non-negative integer counters, timezone-aware ISO timestamp validation, explicit partial-metadata reporting, and a 7-day repository-activity freshness policy (`fresh`/`stale`/`unknown`) are implemented with offline regression tests. Timestamps more than five minutes in the future are rejected. This freshness policy describes repository metadata recency only and does not independently verify claims.
- Technical-analysis coverage for structure, BOS/CHoCH, support/resistance, momentum and risk scenarios; volume must be either implemented correctly or clearly excluded.
- Derivatives: a read-only single-exchange snapshot now covers open interest, funding, mark/index prices and a limited 4-hour OI change. Liquidation totals are explicitly unavailable until continuous event ingestion exists. Multi-exchange derivatives, exchange flows and whale-related evidence remain incomplete.
- News and social sentiment connectors, deduplication, timestamps, manipulation/noise caveats and source links.
- BTC regime and cross-asset/context logic.
- Alerts, scheduling, retry/backoff, notification delivery and user-configurable thresholds.
- Forecast/signal history and outcome evaluation to measure calibration; no unsupported confidence percentages.
- Dashboard/mobile UX and endpoint integration.
- Security, rate limits, observability, error-path tests, reproducible builds and end-to-end validation.
- Final deployment smoke test and rollback plan, only after explicit deployment authorization.


## Findings from source inspection

- **Market data**: the Step 1 adapter calls CoinGecko's public `/coins/markets` endpoint. Rate-limit, outage, and freshness behavior must be checked against its full implementation and tests.
- **Coin screening**: the module tries CoinGecko and falls back to CoinPaprika, maps fallback fields into a common schema, caches successful results briefly, and may serve a bounded stale cache after provider failure. The no-cache failure path preserves separate primary/fallback provider error kinds and HTTP status codes. Stale-cache screening responses include structured primary/fallback provider failure details alongside the backward-compatible `provider_error_code`; fresh-cache/live responses set `provider_error_details` to null. Tests cover failure classification, dual-provider errors, stale-cache timestamps, and endpoint-level serialization of the stale-cache warning and provider details. CI validation on commit `3bd5a5f72d1db275b0b28edce5693ebdc6d2dd7a` completed successfully across all four workflows: screening checks, automated tests, technical-analysis tests, and evidence-ingestion API checks. This validates mocked/offline tests only, not live provider reliability or production readiness; earlier failures on intermediate commits remain part of the history. A screening audit found the fallback previously estimated fully diluted valuation from total supply when max supply was unknown. The fallback now leaves FDV null unless a positive numeric max supply and numeric price are both present; regression tests cover the general market list and commodity scan. Screening responses expose per-asset CIN retrieval timestamps and top-level cache age while preserving the provider's own `last_updated` separately. Regression coverage now also checks fresh/live response metadata and fresh-cache timestamp/cache-age preservation. The commodity-backed scan now retains bounded stale cache after CoinPaprika HTTP, network, or malformed-response failures and surfaces structured provider error metadata; a regression test covers the stale-cache failure response. Code commit `6c4c168012aad414814494188bd342e0b0143338` passed all four GitHub Actions workflows (screening, automated tests, technical analysis, and evidence ingestion). These remain mocked/offline tests; live provider reliability and production behavior are not thereby established. Asset-type labels remain conservative heuristics, not canonical classifications. Commodity scans now preserve structured CoinPaprika failure provenance when a bounded stale cache is used after HTTP, network, or invalid-response failures; endpoint-level regression coverage verifies stale warning, provider error details, and scanned-universe metadata. The stale-cache commodity coverage has passed in prior isolated-branch CI; do not interpret these offline tests as a live-provider or deployment check. Validation on code commit `b638d89ade8be30a0f608ae85da0aa476738bebf` also passed screening, scaffold, technical-analysis and evidence-ingestion workflows. All these CI results are mocked/offline evidence and do not certify live provider data quality or production deployment.
- **Commodity backing assessment**: the API accepts caller-supplied evidence metadata. It does not fetch reserve reports or independently verify custody, solvency, or redemption rights.
- **Growth fundamentals**: the API accepts caller-supplied evidence metadata. Coverage scores are not a substitute for source ingestion or independently verified fundamentals.
- **Evidence ingestion**: the first public connector is limited to an allowlist of three Ethereum-related public GitHub repositories and supports ETH only through the API. This is not yet a general-purpose news, social, whale, exchange-flow, or derivatives ingestion system.
- **Technical analysis**: the caller-supplied OHLC API is deterministic and does not fetch market data itself. Optional per-candle volume now has all-or-none validation and latest/previous-20 average/relative-volume metrics. The public market adapter now forwards volume from closed candles to the analysis engine, with a regression assertion. The latest recorded branch validation passed all four CI workflows on `60a5fa6e87b77edc23240a1863a5aae115613149`; additional regression coverage includes derivatives HTTP rate limits, malformed/crossed order books, empty news results, and news-provider rate limits. These tests are offline/mocked.
- **Derivatives snapshot**: `cin_derivatives_market_data_api.py` adds a read-only Binance USDⓈ-M Futures endpoint for current open interest, latest funding rate, mark/index prices, and an approximate change from the latest two available 4-hour open-interest notional aggregates. It returns provider timestamps separately from CIN retrieval time, classifies provider failures, includes a public order-book snapshot with spread and approximate bid/ask notional imbalance, and explicitly marks liquidations as unavailable because reliable totals require continuous event ingestion. Mocked/offline regression tests are included in scaffold CI. This is a single-exchange snapshot, not a market-wide derivatives model; live-provider validation and deployed-revision verification remain outstanding. An attempted read-only health/readiness check through the available web access path could not access the Render URLs; this does not establish service failure. See `docs/CIN_DERIVATIVES_MARKET_DATA.md`.
- **Public news search**: `cin_public_news_sentiment_api.py` adds a read-only GDELT DOC 2.0 article search endpoint with URL deduplication, provider article timestamps, a transparent keyword-based headline sentiment label, and explicit low-confidence warnings. This is a partial research signal, not a trained financial sentiment model; it does not cover X/social platforms. Mocked/offline tests are included in scaffold CI. Live GDELT and deployed-revision validation remain outstanding. See `docs/CIN_PUBLIC_NEWS_SENTIMENT.md` if present; the API contract is also summarized in `docs/CIN_IMPLEMENTATION_TRACKER.md`.
- **Exchange flows, whale attribution, social-platform sentiment, alerts, and forecast outcome tracking**: no corresponding complete, independently verified end-to-end capability has been established by the source inventory inspected so far. Order-book support remains a single-exchange snapshot, not full cross-exchange liquidity analysis. Treat these as **not yet verified complete**, not as shipped features.

## Practical completion rule

For each planned capability, evidence must include:
1. an implementation path and documented data contract;
2. tests for normal, missing, stale, malformed, and provider-failure cases;
3. source provenance and timestamps in outputs;
4. an explicit unsupported/missing state instead of a fabricated value;
5. confirmation that the running environment serves that exact code revision.

Until those criteria are met, the feature remains partial or unverified.

## Completion accounting

No defensible exact “X complete / Y remaining” count is published here yet. The full numbered roadmap has not been reconciled line-by-line against every source file and live endpoint, and some roadmap requirements may be specifications rather than code. Counting router registrations or passing test files as fully completed modules would overstate progress.

The next audit should create one row per numbered roadmap requirement with columns: requirement ID, source path, acceptance criteria, Designed, Implemented, Tested, Deployed, evidence link, blockers and next action. Only then should a total and percentage be calculated.

## Release controls

- Keep PR #6 unmerged.
- Keep PR #7 unmerged unless separately authorized.
- Do not change Render configuration or trigger deployment without explicit approval.
- Do not introduce trade/order execution, wallet control, private keys, seed phrases or fund movement.
- Prefer free/public sources first; document rate limits and any paid dependency before adopting it.


## Commodity evidence metadata audit — 2026-10-24

The isolated feature branch hardens `commodity_backing_assessment.py`:

- Evidence URLs must be absolute HTTP(S) URLs with a hostname; scheme-only values and URLs containing embedded credentials are rejected for supplied `verified` records.
- Review timestamps earlier than publication are downgraded to `unverified`; future publication timestamps on supplied `verified` growth-fundamentals records are now also downgraded to `unverified`, with regression coverage. These checks validate metadata chronology only, not source claims.
- Outputs include `source_url_valid` and `timestamp_validation_errors` to make the validation result inspectable.
- Regression tests cover these edge cases and a valid HTTP URL.

This is validation of caller-supplied metadata, not independent source retrieval or reserve certification. All four repository workflows passed on code commit `7e26219dc57b752255f6e58e8aefdf1f28e749e1`. These are offline/mocked checks and do not validate live providers or production deployment. No production deployment is implied.


## Growth fundamentals evidence audit — 2026-10-24

The growth fundamentals assessment score is explicitly an evidence-coverage indicator, not a project-quality score or investment recommendation. The assessment accepts caller-supplied metadata and does not fetch source documents or independently verify claims. URL validation now requires a parsed absolute HTTP(S) URL with a hostname; regression tests cover scheme-only URLs, missing hostnames, and a valid HTTP URL. All four GitHub Actions workflows passed on commit `31f8ad04051e15ef028d85ee58f0dd79e2826b9f` (offline tests only). Future publication timestamps on supplied `verified` records are now downgraded to `unverified` with a regression test. This remains caller-supplied metadata validation, not independent fundamentals verification.

## Public evidence ingestion freshness policy — 2026-10-24

The allowlisted GitHub repository connector now validates timestamps as timezone-aware ISO datetimes, rejects timestamps more than five minutes ahead of the local UTC clock, and computes repository-activity recency from pushed_at (falling back to updated_at):

- fresh: selected timestamp is no more than seven days old.
- stale: selected timestamp is older than seven days.
- unknown: neither timestamp is available.
- freshness_age_seconds is the non-negative age of the selected timestamp when available.
- Missing optional metadata is reported as metadata_partial with a missing_fields list; malformed field values produce EvidenceSourceError.

This freshness status describes the selected repository timestamp only. It is not proof of ecosystem-wide development, source truth, investment merit, or independent claim verification. Regression tests are mocked/offline. The exact test commit is 97729aa2d421fcd8fc07cc6a8f277b9d19741fc2; all four GitHub Actions workflows passed for that commit. No live provider check, merge, or production deployment is implied.