# CIN Public Derivatives Market Snapshot

## Endpoint

`GET /derivatives/market-snapshot?symbol=BTCUSDT`

This endpoint is read-only and uses public Binance USDⓈ-M Futures market-data endpoints. It does not request credentials and does not place, amend, or cancel orders.

## Source data

- [Open interest](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest): current contract open interest and provider timestamp.
- [Mark price and funding rate](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price): mark/index prices, latest funding rate, and provider timestamp.
- [Open-interest history](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics): latest two available 4-hour aggregates used for an approximate 4-hour notional open-interest change.
- [Order book](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Order-Book): public depth snapshot used to compute best bid/ask, spread, and approximate bid/ask notional imbalance.

## Data-quality behavior

- Provider timestamps are returned separately from CIN's `retrieved_at`.
- Funding rate is shown as the raw rate and as percentage per funding interval; it is **not annualized**.
- The open-interest change is null when the provider does not return two usable aggregates or the previous notional value is non-positive.
- HTTP, network, and malformed-response failures return structured API errors rather than fabricated numbers.
- Liquidation totals are explicitly marked `not_available`. A reliable liquidation window requires continuous event ingestion and aggregation; this point-in-time snapshot does not infer liquidation totals.
- Order-book metrics are a rapidly changing snapshot; the public endpoint excludes retail price-improvement orders.
- This is one exchange's derivatives market, not a market-wide aggregate.

## Validation boundary

The automated tests mock provider payloads and failure paths. They validate mapping and error handling, not live Binance reachability, live values, regional availability, or production deployment. Live read-only smoke validation remains outstanding until a network-enabled validation environment is available.

- Malformed, non-finite, or non-positive order-book levels are excluded from calculations and their rejected counts are exposed as `order_book.bid_levels_rejected` and `order_book.ask_levels_rejected`; this prevents a partially malformed depth payload from looking indistinguishable from a fully usable book.
- Empty open-interest history is valid but yields null history-derived notional and change values, and a null latest-history timestamp. No change is inferred when there are no history points.

## Timestamp freshness contract

The response keeps the original provider timestamps in `provider_timestamps` and adds `timestamp_quality` metadata for each timestamped source. Each quality record includes the ISO timestamp, age in seconds, status, and applicable thresholds.

- Open interest and mark-price/funding timestamps are marked `stale` when older than 15 minutes.
- The latest 4-hour open-interest history aggregate is marked `stale` when older than 8 hours.
- Provider timestamps more than 60 seconds in the future are marked `future_dated`; this does not silently relabel them as fresh.
- A missing history timestamp is `unavailable`, not an invalid provider timestamp. Because unavailable timestamps are conservatively included in `freshness_warnings`, empty history makes `freshness_status` a `warning` and `analysis_eligibility` `not_recommended`; history-derived metrics remain null.
- `data_quality.freshness_status` is `warning` if any source timestamp is stale, future-dated, or invalid; `freshness_warnings` names the affected sources. The endpoint retains the snapshot but callers should not treat a warned snapshot as fully fresh.

These thresholds are CIN heuristics, not exchange guarantees. Automated tests use fixed timestamps and mocked payloads; live provider clock behavior remains unverified.


### Analysis eligibility when timestamp evidence is incomplete

`data_quality.freshness_status` is `warning` if any timestamp-quality component is stale, future-dated, invalid, or unavailable. The response also exposes `data_quality.analysis_eligibility`: `eligible` only when all tracked timestamp checks are acceptable, otherwise `not_recommended`, with a reason. This is a conservative consumer-facing warning, not a hard endpoint failure; the raw snapshot remains available for inspection. In particular, empty open-interest history leaves history-derived metrics null and must not be interpreted as a clean freshness result. Offline tests do not establish live provider availability.
