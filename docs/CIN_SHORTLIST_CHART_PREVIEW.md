# Shortlist chart integration preview

The optional `GET /research/shortlist-chart-preview/{asset_id}?horizon=24h` route is disabled unless `CIN_SHORTLIST_PREVIEW_ENABLED` is exactly `1`. Supported assets are bitcoin and ethereum; horizons are 1h, 6h, 12h, 24h and 7d.

When enabled, it calls CIN's public candle API for an explicit USDT market and validates the returned closed-candle window. A validated chart is not a complete shortlist. The response explicitly marks market, news, social and market sentiment as unassessed and returns no forecast or probability. Provider identity is not independently verified.

A five-minute per-process cache and one-minute per-key failure backoff limit repeated requests within one worker. They do not provide a distributed rate limit. Treat returned cache age and chart observation time independently; cached chart data may age. Access, operational budget, freshness policy, source terms and provider identity must be reviewed before activation. Keep disabled until staging validation and integration are complete.


## Explicit USD market evidence

The optional query parameter `quote=USD` requests a BTCUSD or ETHUSD chart and attempts to attach a Coinbase USD ticker from the existing market-data API. The ticker must match the exact asset, product and quote and pass freshness checks. A failure leaves market evidence missing; it does not erase a valid chart. `quote=USDT` remains the default and never substitutes a Coinbase USD price. Chart and ticker can come from different exchanges and are not an atomic snapshot. News, social and market sentiment are not yet integrated and the result is not eligible for a shortlist.

