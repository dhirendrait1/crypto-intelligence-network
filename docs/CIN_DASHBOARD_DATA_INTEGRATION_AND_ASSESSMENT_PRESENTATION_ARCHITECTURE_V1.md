# CIN Dashboard Data Integration and Assessment Presentation Architecture (F-20)

**Status:** Architecture/readiness design only  
**Date:** 2026-10-31  
**Roadmap alignment:** Stage 6, especially Step 30 (mobile-first dashboard flow/API-to-screen mapping), with dependencies on Steps 31–33. This F-20 increment does not add a new numbered roadmap step.

## 1. Purpose and implementation boundary

Define how a future CIN dashboard consumes existing read-only API families and presents market context, assessment results, evidence quality, and monitoring state without converting incomplete or heuristic outputs into misleading signals.

Repository inventory review found backend modules, routers, deployment scaffold material, tests, and documentation, but no independently maintained dashboard/frontend/static/template source tree in the inspected branch. The implementation tracker also records dashboard/mobile UX as not established. Therefore this document is a target integration architecture, not a claim that a dashboard exists or is deployed.

No frontend code, API route, response schema, provider, scoring formula, persistence, deployment, Render configuration, or Cloudflare configuration is changed by this increment.

## 2. Dashboard product principles

1. **Research-first and read-only:** present evidence, analysis, monitoring and alerts; never place orders, route orders, control wallets, or move funds.
2. **Mobile-first:** design for narrow Android screens and one-handed navigation, with progressive disclosure for dense provenance.
3. **Evidence before interpretation:** show source, observation time, retrieval time, freshness, coverage and limitations next to the result.
4. **No synthetic certainty:** never convert missing, stale, partial, conflicting or unsupported data into zero, neutral, false, complete or a confident signal.
5. **Graceful degradation:** one provider/module failure must not hide valid independent panels.
6. **Low-bandwidth aware:** bound requests, avoid repeated polling, cache only with visible age, and make refresh user-controlled or governed by a documented schedule.
7. **Traceable outputs:** retain contract version, assessment identity, methodology version and snapshot lineage when supplied by the API.
8. **Accessible semantics:** status must be readable as text and not conveyed by color alone.

## 3. Proposed information architecture

### Primary navigation

- **Overview** — BTC/ETH and selected-market context, system data health, recent material alerts.
- **Markets** — public spot market summary, pair/timeframe selection, candles and descriptive metrics.
- **Screening** — ranked/filtered assets with component explanations, exclusions and data-quality holds.
- **Analysis** — technical analysis, derivatives snapshot and scenario context.
- **Research** — commodity backing, growth fundamentals, cross-source comparisons and evidence drill-down.
- **News** — timestamped headlines and explicitly low-confidence headline sentiment.
- **Alerts** — configured rules, triggered events, delivery state and history when implemented.
- **System health** — provider status, API health/readiness, freshness and known limitations.

Navigation items for capabilities not implemented must be hidden or visibly marked planned/disabled; a placeholder must not masquerade as a working feature.

### Overview screen hierarchy

1. Global read-only and data-as-of banner.
2. Market context strip: selected pair, quote currency, timeframe, latest completed candle time and freshness.
3. Data health summary: provider states, stale/partial/unavailable counts and last successful retrieval.
4. Key research cards: screening, technical analysis, derivatives and news, each showing its own source/time/status.
5. Material alerts and unresolved conflicts.
6. Recent assessment activity and links to provenance.

No single global “market confidence” score should be synthesized from heterogeneous modules.

## 4. API-to-screen mapping

| Screen/panel | API family | Required display context | Safe fallback |
|---|---|---|---|
| Market overview | `/market-data` and market-candle routes | Pair, quote currency, provider, observed/retrieved time, cache age, candle completeness | Preserve valid rows; mark missing metrics unavailable |
| Screening | `/coin-screening` | Universe/scan coverage when known, score components, provider/fallback, cache age, exclusions/holds | Show partial list with explicit coverage warning; never imply full-market scan |
| Technical analysis | `/technical-analysis`, `/technical-analysis/market` | Input source, timeframe, candle count, forming-candle exclusion, indicator availability and scenario caveats | Hide unavailable indicators; distinguish caller-supplied from exchange-retrieved candles |
| Derivatives | derivatives snapshot route | Exchange, observation/retrieval time, funding/OI window, order-book depth scope, unavailable liquidation data | Show fields independently; never infer liquidation totals |
| Commodity backing | `/commodity-backing-assessment` | Caller-supplied evidence mode, category coverage, freshness, source-role authentication, non-certification warning | Empty/partial evidence shown as unknown or incomplete |
| Growth fundamentals | `/growth-fundamentals-assessment` | Category denominator, evidence coverage, reporting periods, units, source status | No evidence is “not assessed”, not zero growth |
| Cross-source comparison | `/cross-source-evidence-comparison` | Metric/unit, comparison window/tolerances, comparability and independence caveats | Keep conflicts visible; no automatic preferred source |
| News | `/news-sentiment` | Provider-seen time vs publication time, language status, source URL, heuristic caveat | Unknown timestamp/language stays unknown; unsupported language is unavailable |
| System health | `/health`, `/ready` plus per-provider metadata | API health and data-provider health separately | API healthy does not imply providers/data are fresh |

Route names must be checked against the deployed OpenAPI document before a frontend binds to them. This mapping is based on repository modules and docs; it is not evidence of live endpoint availability.

## 5. Shared client-side data model

The dashboard should normalize API responses into a presentation model without changing their meaning:

- `resource_key`: module + entity/pair + timeframe/query.
- `request_state`: idle, loading, success, empty, partial, stale, error.
- `contract_version`: exact server response contract version, when available.
- `source_state`: provider, caller_supplied, cache, fallback, or unknown.
- `observed_at`, `retrieved_at`, `assessment_clock`: separate nullable timestamps.
- `freshness`: fresh, stale, unknown, unavailable.
- `coverage`: status, denominator, observed, missing and excluded fields only when supplied.
- `limitations` and `warnings`: retained, not dropped during normalization.
- `payload`: module-specific data retained without lossy coercion.

Normalization must not fill missing numeric values with zero, missing booleans with false, absent arrays with evidence of an empty scan, or unknown statuses with success. A zero is displayed only when the API explicitly supplies a measured/calculated zero with defined semantics.

## 6. Refresh, cache and low-bandwidth policy

- Fetch on screen entry and on explicit refresh; background refresh intervals require a separate measured resource budget and user-visible policy.
- Use bounded timeouts and avoid overlapping duplicate requests for the same resource key.
- Preserve server/provider timestamps and cache age. A client fetch time is not a replacement for source observation time.
- Cache only responses whose semantics permit it. Store fetched-at time and contract version with every cache entry.
- Mark cached content stale after the server-defined freshness threshold or when that threshold is unknown; do not invent a universal threshold across different data types.
- Do not silently replace a failed fresh request with stale content. If stale cache is shown, label it prominently and retain the failure reason.
- Support manual refresh, request cancellation on navigation, exponential backoff with jitter for retryable errors, and a cap on retry attempts.
- Avoid polling endpoints that trigger expensive provider work. Use conditional requests/ETags only if supported by the API.
- Respect provider rate limits; client retries must not amplify them.

## 7. Loading, empty, partial, stale and error states

Every data panel must implement these distinct states:

- **Loading:** skeleton/placeholder plus panel identity; no fabricated values.
- **Empty:** successful response with explicitly empty result and a known scope; explain the scope.
- **Not assessed:** no assessment/evidence was supplied or no evaluation was performed.
- **Partial:** some expected fields/sources/entities are absent; show missing coverage.
- **Stale:** value exists but exceeds the applicable freshness policy; show age and source time.
- **Conflicting:** sources disagree; preserve source-specific values and comparison context.
- **Unavailable:** provider/feature cannot supply the requested information.
- **Error:** request failed; show safe error category and retry action only when retryable.
- **Unknown:** the system cannot determine the state; do not coerce it to neutral or success.

Panel status must be independent: a news outage must not mark candles unavailable, and API readiness must not imply data-provider freshness.

## 8. Visualization and interpretation rules

- Candlestick charts must label exchange/provider, pair, quote currency, timeframe, latest completed candle and any forming candle treatment.
- Gaps must remain gaps; do not interpolate missing market candles as observed prices.
- Technical indicators must state their lookback and show unavailable when insufficient bars exist.
- Support/resistance and swing levels are reference levels, not verified resting liquidity.
- Funding, open interest, spread and depth must show venue, units, timestamp and sampling limitations.
- News sentiment must be labelled headline-only heuristic and low confidence; provider-seen time must not be presented as verified publication time.
- Screening ranks must expose score components, exclusions and universe coverage; ranking is not a recommendation.
- Commodity and growth evidence coverage must show denominator and missing categories; coverage is not quality or truth.
- Cross-source comparison must display conflict and independence limitations; no silent source selection.
- Alerts must distinguish detected condition, evaluation time, delivery status and acknowledgment state. A detected condition is not an instruction to trade.

## 9. Alert and monitoring presentation

When alert functionality is implemented, the dashboard should display:
- rule name/version and user-defined threshold;
- asset/metric/timeframe and evaluation timestamp;
- observed value, comparison operator and threshold with units;
- source and freshness at trigger time;
- deduplication/cooldown state;
- delivery channel, attempt count, last attempt and delivery/failed/unknown state;
- acknowledgment/snooze state, if implemented.

Do not display “delivered” merely because an alert condition was evaluated. Do not claim push/Telegram delivery until the delivery provider confirms it. No alert may trigger order execution.

System health should separate API process health, readiness, each data provider, cache state, ingestion lag and notification delivery. A single green “system online” badge is insufficient.

## 10. Security, privacy and accessibility

- No exchange account credentials, wallet connections, seed phrases or private keys.
- Keep provider secrets server-side if a future authorized connector requires them; never embed secrets in frontend bundles.
- Restrict external link rendering to safe HTTP(S) URLs and open links with appropriate browser isolation.
- Avoid rendering untrusted HTML from headlines, source names, notes or claim text.
- Do not expose stack traces, internal paths, environment variables or provider response bodies.
- Minimize browser storage; avoid retaining sensitive query history without a defined purpose and retention rule.
- Provide text labels, screen-reader status announcements, keyboard access, adequate contrast, chart summaries and tabular alternatives.
- Layout target: narrow mobile viewport first, then tablet/desktop enhancement; test Android browser behavior and slow/intermittent connectivity.

## 11. Implementation and acceptance sequence

1. Confirm actual deployed OpenAPI routes and contract versions against the selected backend revision.
2. Implement a thin API client with typed request/response models and centralized timeout/error handling.
3. Build shared status/provenance components before individual dashboard cards.
4. Implement Overview and Markets using only endpoints with verified contracts.
5. Add Screening and Analysis panels with module-specific limitations.
6. Add Research evidence panels and provenance drill-down.
7. Add News with language and provider timestamp caveats.
8. Add Alerts only after rule evaluation and delivery-state APIs exist.
9. Add system-health view separating process readiness from provider freshness.
10. Run contract, visual, accessibility, mobile viewport, offline/slow-network and stale-cache tests.

Acceptance requires each panel to preserve API semantics, show source and time context, handle all nine data states, remain usable at mobile widths, and avoid unsupported claims. No dashboard screen is production-ready until it is tested against the exact deployed API revision.

## 12. Explicit non-actions and remaining work

This increment is architecture only. No frontend implementation, API integration, chart, alert engine, persistence, provider, response schema, deployment or configuration was changed. No Render/Cloudflare actions were taken.

**F-20 outcome:** Dashboard data integration and assessment presentation architecture documented. Actual mobile dashboard, shared client, state components, charts, alert views and end-to-end validation remain unimplemented. Stage 6 Steps 30–33 remain pending until code and tests exist.
