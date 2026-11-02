# CIN Mobile Dashboard — Stage 6 Contract

## Status and connection behavior
This is a responsive dashboard preview with an optional, user-initiated API connection. It does not fetch live data on page load. No API request is made until the user explicitly enters an API origin and selects **Connect API**. Disconnect aborts in-flight requests and returns panels to an unverified state.

The connection is informational and read-only: the dashboard sends GET requests only, omits credentials, rejects redirects, disables caching, and validates the supplied API origin before requesting data. A successful HTTP response alone does not prove source authenticity, data correctness, or freshness. The dashboard must not present illustrative chart geometry or network nodes as live measurements.

The dashboard preview is not proof that it is served by the production application or that the configured API origin is deployed and reachable. Deployment integration remains unverified until separately tested.

## Dashboard sections
- Market data: provider, symbol, interval, observed/retrieved timestamps, candle closure state.
- Technical analysis: timeframe, closed-candle status, trend/structure, indicator values, input candle count.
- Coin screening: score, methodology/version, inputs, source timestamps, limitations.
- Evidence and provenance: source identity, evidence type, observation/retrieval times, freshness and completeness.
- News and derivatives: source and publication/retrieval timestamps, coverage limitations.
- Monitoring: health/readiness, source-specific freshness policy, explicit unknown/unconfigured state.

## Configured read-only requests
All configured requests use GET and are issued only after explicit user action:

| Panel | Path | Key response contract |
|---|---|---|
| Market candles | `/market-candles?symbol=BTCUSDT&interval=1h&limit=50` | `symbol`, `timeframe`, `count`, `source`, `retrieved_at`, `data[]`, candle closure and freshness metadata |
| Technical analysis | `/technical-analysis/market?symbol=BTCUSDT&interval=1h&limit=100` | `input.symbol`, `input.timeframe`, `input.source`, `input.retrieved_at`, analysis and indicator fields |
| Coin screening | `/coin-screening?vs_currency=usd&per_page=5&min_score=0&asset_type=growth` | `count`, `source`, `data_mode`, `retrieved_at`, `methodology`, `data[]` |
| Public news sentiment | `/news-sentiment?query=cryptocurrency&max_records=5` | `count`, `sentiment_summary`, `source`, `retrieved_at`, article timestamps |
| Derivatives snapshot | `/derivatives/market-snapshot?symbol=BTCUSDT` | `symbol`, `source`, `retrieved_at`, `data_quality.freshness_status`, `timestamp_quality` |

These are configured client paths and expected fields, not a claim that every route is present in every deployed build. Verify the target application's OpenAPI document and route registration before treating a panel as integrated. Coin screening provider behavior must also be checked against the active provider-specific implementation; do not assume the preview's branch includes later provider changes.

## Response-state contract
Every API-backed panel must support:
- `loading`: request in progress.
- `available`: valid response with source and timestamp metadata; label it API-reported, not independently verified.
- `partial`: response is usable but incomplete; enumerate missing fields.
- `stale`: only when a configured source/data-type policy establishes the threshold.
- `unknown`: freshness cannot be established or no policy is configured.
- `unavailable`: request failed or endpoint/provider is unavailable.
- `invalid`: response failed schema/contract validation.

Never infer `fresh` from a successful HTTP response alone. Never convert missing data to zero. Keep error messages safe and concise; do not expose secrets. Keep unknown, stale, partial and unverified states visible.

## Integration requirements before release
1. Confirm all five routes and their methods/response fields against the exact target build's OpenAPI document.
2. Add automated API-contract tests for success, empty, partial, stale, unknown, unavailable and malformed responses, including missing required metadata.
3. Render provider/source IDs and UTC timestamps with each dataset.
4. Confirm mobile accessibility, keyboard focus, readable contrast and narrow-screen layout on a real Android device.
5. Verify the dashboard is served by the intended application before calling it deployed.
6. Keep Render configuration/deployment under the project owner's control.

## Security boundaries
No order placement or execution, order management, wallet control, private keys, seed phrases or fund movement. The dashboard is an informational interface only.
