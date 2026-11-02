# CIN Mobile Dashboard API-to-Screen Contract

**Roadmap:** Stage 6, Step 30 — define the mobile-first dashboard flow and API-to-screen mapping.  
**Status:** Acceptance contract only; it does not claim a frontend has been implemented.  
**Safety boundary:** Read-only public intelligence. No account trading, order execution, wallet control, fund movement, or secrets.

## 1. Primary mobile navigation

Use a small-screen-first navigation model with these destinations:

1. **Overview** — service status, market summary, latest update time, and data-quality warnings.
2. **Screening** — ranked assets with score methodology, source, quote currency, and exclusions.
3. **Analysis** — selected asset, interval, candle provenance, indicator values, and explicit limitations.
4. **Research** — news, fundamentals, and backing assessments with claim/evidence separation.
5. **Alerts** — configured rules and their evaluation/delivery state; never an execution action.

Hide destinations that the running API does not support. A route existing in OpenAPI is not proof that its data is reliable or complete.

## 2. API-to-screen mapping

| Screen | Data contract | Required visible context | Fallback |
|---|---|---|---|
| Overview | Health/readiness plus market-data response | API status, source, retrieved/observed time when available, quote currency, freshness | Show service state separately from market-data state; never infer market health from API health |
| Screening | Screening rows and metadata | Asset identity, rank/score semantics, provider, quote currency, freshness, warnings/exclusions | Show a partial-result notice or explicit unavailable state; never fabricate missing rows |
| Analysis | Supplied/returned OHLC candles and indicator output | Pair, interval, source, candle count, last closed-candle time, analysis method, limitations | Do not render indicators as current if candle freshness/closure is unknown |
| Research | News/fundamentals/backing evidence | Source citation, claim vs verified fact, observed time, retrieval time, confidence/quality reason | Mark unsupported claims as unverified; do not imply issuer/reserve claims are proven by heuristic scores |
| Alerts | Rule evaluation and delivery-state records, when implemented | Rule, metric/unit, evaluated time, freshness/conflict state, dedupe/cooldown and delivery state | Distinguish “triggered” from “delivered”; if persistence or sending is not implemented, say so |

The mapping above describes the target interface. It does not imply that every endpoint, field, alert channel, or screen exists in the current deployment.

## 3. Shared response envelope for UI adapters

A future frontend adapter should normalize endpoint-specific payloads into a presentation envelope without changing source values:

- `capability`: stable feature identifier.
- `state`: one of `loading`, `ready`, `empty`, `partial`, `stale`, `error`, or `unavailable`.
- `data`: original typed payload or null; do not coerce unknown fields to zero.
- `source`: provider/source identity when known.
- `observed_at`: source observation timestamp when provided.
- `retrieved_at`: retrieval timestamp when provided.
- `freshness`: `fresh`, `stale`, or `unknown`; do not derive “fresh” without a documented endpoint-specific threshold.
- `warnings`: machine-readable reasons plus user-readable descriptions.
- `request_id`: optional correlation identifier if the API provides one.

This is a frontend adapter contract, not a demand to change existing API response shapes in this step. Missing provenance must remain unknown rather than being filled with guessed values.

## 4. State semantics

- **loading:** request is in progress; retain prior data only if clearly labelled as previous.
- **ready:** usable data was returned and passed the endpoint's acceptance checks.
- **empty:** request succeeded and explicitly returned no qualifying results.
- **partial:** some usable results exist, but warnings/exclusions indicate incomplete coverage.
- **stale:** data exists but exceeds the documented freshness policy.
- **error:** the request failed; show a sanitized message and retry affordance where safe.
- **unavailable:** capability is not implemented or is intentionally disabled. Do not represent this as an empty result.

State priority when multiple conditions apply: `error` for a failed current request, otherwise `unavailable` for an unsupported capability, otherwise `stale` when data is known stale, otherwise `partial` when incomplete, otherwise `empty` for a confirmed empty success, otherwise `ready`. A UI may separately preserve and label last-known data while a refresh fails.

## 5. Android and low-bandwidth requirements

- Design for narrow screens and vertical scrolling; avoid requiring horizontal table scrolling for core tasks.
- Keep primary status, asset identity, source, timestamp, and warnings readable without opening a detail view.
- Request only the fields needed by the active screen when the API supports selective fields.
- Avoid rapid polling by default; use bounded refresh and explicit retry controls.
- Preserve the last successful response only with its original timestamp and a visible stale/previous-data label.
- Use accessible text labels and icons; never communicate state by color alone.
- Provide explicit units and quote currencies. Do not equate USD and USDT.
- Sanitize provider errors and never expose credentials, internal stack traces, or secret configuration.

## 6. Acceptance tests required before implementation is called complete

1. Every screen maps only to a verified endpoint/capability; unsupported screens are hidden or labelled unavailable.
2. API health and market-data freshness are displayed as separate dimensions.
3. Missing timestamps/source fields render as “unknown” rather than invented values.
4. Stale, partial, empty, error, and unavailable states have distinct UI behavior.
5. A refresh failure cannot silently relabel cached data as current.
6. Numeric values retain units, quote currency, and provider identity.
7. A screening rank is not described as a probability or investment guarantee.
8. Analysis displays interval and closed-candle/freshness context where supplied; otherwise it discloses unknown context.
9. Alert “triggered”, “queued”, “delivered”, “retrying”, and “failed” states are not conflated.
10. No screen includes order placement, wallet connection for control, fund movement, or private-key entry.
11. Smoke tests cover narrow Android viewport, low bandwidth, long source labels, and large warning text.
12. Tests and screenshots are tied to a specific revision; offline tests do not count as live deployment verification.

## 7. Completion boundary

This contract completes only the design/acceptance definition for Step 30 when reviewed and merged. Steps 31–33 still require implemented UI states, accessible visualizations, and small-screen/low-bandwidth validation. Production readiness remains subject to separate live checks and explicit deployment authorization.
