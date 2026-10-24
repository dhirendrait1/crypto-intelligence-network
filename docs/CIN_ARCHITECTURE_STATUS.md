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

The deployment patch `patch_cin_metadata_fixed.py` names the following source modules and registers seven router families in the FastAPI application.

| Component | Source module(s) | Evidence/status |
|---|---|---|
| Public market data | `market_data_step1.py` | Named in deployment patch; full behavior audit pending |
| Coin screening | `coin_screening_step2.py` | Named in deployment patch; full behavior audit pending |
| Commodity backing assessment | `commodity_backing_assessment.py`, `commodity_backing_api.py` | Named in deployment patch; full behavior audit pending |
| Growth fundamentals | `growth_fundamentals_assessment.py`, `growth_fundamentals_api.py` | Named in deployment patch; full behavior audit pending |
| Public evidence ingestion | `cin_evidence_ingestion.py`, `cin_evidence_ingestion_api.py` | Named in deployment patch; full source and allowlist audit pending |
| Caller-supplied OHLC analysis | `cin_technical_analysis.py`, `cin_technical_analysis_api.py` | Named in deployment patch; prior offline technical-analysis checks passed; full feature audit pending |
| Exchange-backed candle data and analysis | `cin_public_market_candles_api.py` | Market-data branch regression tests passed previously; wording fix added on this branch and requires CI re-run |
| API health/readiness | FastAPI app endpoints | Live `/health` and `/ready` returned healthy/ready in earlier checks; recheck after any future release |

The patch copies the source modules into `cin/app` during the build. The source inventory therefore needs to be audited together with the generated scaffold and patch process.

## Market-data acceptance criteria

- Provider name and endpoint are explicit.
- Actual provider pair key and quote currency are reported when reliably known.
- Every candle reports UTC open/close timestamps and closed/forming state.
- Analysis excludes forming candles and reports requested, used and excluded counts.
- Unsupported fallback intervals/pairs fail clearly; no fabricated fallback data.
- Missing, stale, partial or unverified inputs are surfaced instead of silently guessed.
- Volume is not represented as an active indicator input until the analysis code actually uses it.
- Swing highs/lows are described as reference levels, not verified resting liquidity.
- Tests use mocks/offline fixtures and never place orders or access private accounts.

## Current verified test evidence

Previously recorded CI on the market-data validation branch:
- Scaffold tests: 11 passed.
- Market-data regression tests: 13 passed.
- Technical-analysis offline checks: passed.
- Screening and evidence-ingestion offline checks: passed.

These results apply to the recorded branch commit and tests at that time. The subsequent closed-candle limitation wording/test update on `feat/cin-architecture-audit` needs its own CI run. Mocked tests do not certify all live exchange pairs, provider uptime, or production behavior.

## Work still requiring verification or implementation

The following are not marked complete until code and evidence are inspected:

- Full source review of screening and assessment algorithms, including inputs, scoring rationale and missing-data behavior.
- Full audit of evidence ingestion source allowlists, timeouts, source attribution, parsing failures and freshness.
- Technical-analysis coverage for structure, BOS/CHoCH, support/resistance, momentum and risk scenarios; volume must be either implemented correctly or clearly excluded.
- Derivatives data (open interest, funding and liquidations), exchange flows and whale-related evidence, with provider coverage and caveats.
- News and social sentiment connectors, deduplication, timestamps, manipulation/noise caveats and source links.
- BTC regime and cross-asset/context logic.
- Alerts, scheduling, retry/backoff, notification delivery and user-configurable thresholds.
- Forecast/signal history and outcome evaluation to measure calibration; no unsupported confidence percentages.
- Dashboard/mobile UX and endpoint integration.
- Security, rate limits, observability, error-path tests, reproducible builds and end-to-end validation.
- Final deployment smoke test and rollback plan, only after explicit deployment authorization.


## Findings from source inspection

- **Market data**: the Step 1 adapter calls CoinGecko's public `/coins/markets` endpoint. Rate-limit, outage, and freshness behavior must be checked against its full implementation and tests.
- **Coin screening**: the screening module uses CoinGecko market data and conservative symbol/name heuristics for some asset-type labels. Its own source comments say the taxonomy is not canonical or independently verified. Screening output must preserve that caveat.
- **Commodity backing assessment**: the API accepts caller-supplied evidence metadata. It does not fetch reserve reports or independently verify custody, solvency, or redemption rights.
- **Growth fundamentals**: the API accepts caller-supplied evidence metadata. Coverage scores are not a substitute for source ingestion or independently verified fundamentals.
- **Evidence ingestion**: the first public connector is limited to an allowlist of three Ethereum-related public GitHub repositories and supports ETH only through the API. This is not yet a general-purpose news, social, whale, exchange-flow, or derivatives ingestion system.
- **Technical analysis**: the caller-supplied OHLC API is deterministic and does not fetch market data itself. On this branch, optional per-candle volume was added with all-or-none validation and latest/20-candle average/relative-volume metrics. The market-backed endpoint is a separate adapter; volume metrics must still be checked for consistency with its output schema and covered by CI.
- **Derivatives, order-book depth, exchange flows, whale attribution, news/social sentiment, alerts, and forecast outcome tracking**: no corresponding complete, independently verified end-to-end capability has been established by the source inventory inspected so far. Treat these as **not yet verified complete**, not as shipped features.

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
