# Shortlist chart integration preview

The optional `GET /research/shortlist-chart-preview/{asset_id}?horizon=24h` route is disabled unless `CIN_SHORTLIST_PREVIEW_ENABLED` is exactly `1`. Supported assets are bitcoin and ethereum; horizons are 1h, 6h, 12h, 24h and 7d.

When enabled, it calls CIN's public candle API for an explicit USDT market and validates the returned closed-candle window. A validated chart is not a complete shortlist. The response explicitly marks market, news, social and market sentiment as unassessed and returns no forecast or probability. Provider identity is not independently verified.

A five-minute per-process cache and one-minute per-key failure backoff limit repeated requests within one worker. They do not provide a distributed rate limit. Treat returned cache age and chart observation time independently; cached chart data may age. Access, operational budget, freshness policy, source terms and provider identity must be reviewed before activation. Keep disabled until staging validation and integration are complete.

