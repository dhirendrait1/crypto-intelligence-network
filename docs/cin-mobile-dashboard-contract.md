# CIN Mobile Dashboard — Stage 6 Contract

## Status
This is a static, responsive UI preview. It intentionally does not call the live API, show fabricated market values, or claim deployment integration.

## Dashboard sections
- Market data: provider, symbol, interval, observed/retrieved timestamps, candle closure state.
- Technical analysis: timeframe, closed-candle status, trend/structure, indicator values, input candle count.
- Coin screening: score, methodology/version, inputs, source timestamps, limitations.
- Evidence and provenance: source identity, evidence type, observation/retrieval times, freshness and completeness.
- News and derivatives: source and publication/retrieval timestamps, coverage limitations.
- Monitoring: health/readiness, source-specific freshness policy, explicit unknown/unconfigured state.

## Response-state contract
Every API-backed panel must support:
- `loading`: request in progress.
- `available`: valid response with source and timestamp metadata.
- `partial`: response is usable but incomplete; enumerate missing fields.
- `stale`: only when a configured source/data-type policy establishes the threshold.
- `unknown`: freshness cannot be established or no policy is configured.
- `unavailable`: request failed or endpoint/provider is unavailable.
- `invalid`: response failed schema/contract validation.

Never infer `fresh` from a successful HTTP response alone. Never convert missing data to zero. Keep error messages safe and concise; do not expose secrets.

## Integration requirements before release
1. Connect panels to documented read-only endpoints and validate response schemas.
2. Render provider/source IDs and UTC timestamps with each dataset.
3. Add tests for loading, empty, partial, stale, unknown, unavailable and malformed responses.
4. Confirm mobile accessibility, keyboard focus, readable contrast and narrow-screen layout.
5. Verify the dashboard is served by the intended application before calling it deployed.
6. Keep Render configuration/deployment under the project owner's control.

## Security boundaries
No order placement or execution, order management, wallet control, private keys, seed phrases or fund movement. The dashboard is an informational interface only.
