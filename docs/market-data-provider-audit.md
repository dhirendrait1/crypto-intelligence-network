# CIN market-data provider audit

**Status:** implementation inventory and migration decision; not a provider switch.

## Current provider inventory (verified from source on `main`)

| Capability | Current order | Data required | Policy finding |
|---|---|---|---|
| Public candles | Binance primary; Kraken fallback; Coinbase fallback after the preceding providers fail (including Binance HTTP 451) | OHLCV candles, timestamps, symbol and interval | Not Coinbase-first. Coinbase fallback supports a limited interval set: `1m`, `5m`, `15m`, `1h`, `6h`, `1d`. Product/quote mapping must be explicit; USD must never stand in for USDT. |
| Coin screening | CoinGecko markets primary; CoinPaprika tickers fallback | Market-cap rank/value, quote-currency price, volume, supply, 24-hour change, asset identity | Candle APIs are not equivalent to a ranked market-universe endpoint. Do not replace this with Coinbase candles. |
| Commodity-backed asset scan | CoinPaprika ticker data is used by a separate screening path | Asset identity, market data, heuristic asset classification | A market ticker does not verify reserves, custody, redemption rights or issuer claims. Classification is explicitly heuristic. |
| Derivatives snapshot | Separate derivatives module; inspect its adapter/source mappings before any provider-policy change | Derivatives-specific metrics, not spot OHLCV alone | Must be audited separately; spot candle providers cannot substitute for derivatives data. |
| News sentiment | Separate public news/RSS ingestion module | Article identity, publication time, source attribution, sentiment evidence | Not a market-price provider; keep its source policy separate. |

## Screening data contract (Phase B)

The current `/coin-screening` implementation needs a ranked market universe and the following fields. The contract below distinguishes provider observations from derived or heuristic values; missing evidence must remain missing rather than being invented.

| Field / output | Expected meaning | Source status and validation |
|---|---|---|
| `id` | Stable provider-specific asset identifier | Provider-reported; required for identity deduplication. Do not assume IDs are portable across providers. |
| `symbol`, `name` | Asset display metadata | Provider-reported, non-canonical; never use symbol alone as identity. |
| `market_cap` | Market capitalization in selected quote currency | Provider-reported; quote currency and timestamp must be explicit. |
| `current_price` / output `price` | Latest provider price in selected quote currency | Provider-reported; preserve quote asset and provenance. |
| `total_volume` / output `total_volume_24h` | Reported 24-hour trading volume | Provider-reported; exchange/universe coverage may differ by provider. |
| `circulating_supply`, `total_supply`, `max_supply` | Supply observations | Provider-reported where available; unknown values remain null. |
| `fully_diluted_valuation` | Provider-reported FDV or explicitly derived price × positive max supply | If derived, mark as derived and record the inputs; never substitute total supply for unknown max supply. |
| `price_change_percentage_24h` | 24-hour change in the requested quote market | Provider-reported; do not compare values with differing windows or quote currencies as if identical. |
| `last_updated` | Provider's observation/update timestamp | Provider-reported; parse timezone explicitly. Retrieval time is not observation time. |
| `provider`, `quote_currency`, `provider_retrieved_at` | Source attribution and retrieval metadata | CIN metadata; provider and quote must match the actual response path. |
| `freshness_status`, `analysis_eligible` | Freshness classification and whether data can support analysis | CIN-derived policy output; stale cache must not be presented as fresh or eligible. |
| `volume_to_market_cap`, `fdv_gap_ratio`, `circulating_supply_ratio` | Derived screening metrics | Derived from validated finite inputs; return null and a warning when inputs are absent/invalid. |
| `asset_type`, `screen_band`, `screen_score` | Preliminary classification and heuristic ranking | CIN heuristics, not provider facts, verified taxonomy, investment advice, or a safety rating. |

### Ranking and coverage constraints

- A Coinbase public candle endpoint returns candle observations for a requested product/interval; it does not by itself provide the ranked all-market universe required by `/coin-screening`.
- Do not fabricate market-cap ranking, supply, volume, FDV, or 24-hour change from OHLC candles.
- A provider migration for screening is acceptable only if the candidate source supplies the required universe and field semantics, or if the API explicitly reports unsupported fields and reduced coverage.
- Provider identity, quote currency, observation timestamp, retrieval timestamp, cache state, and fallback provider must remain distinguishable in the response.
- Missing values receive no score contribution. Derived metrics must use finite values and disclose their calculation.

## Required offline adapter tests before any provider default changes

1. **Schema and identity:** valid payload, malformed payload, empty response, missing identity, duplicate IDs, and ambiguous symbol collisions.
2. **Quote/product mapping:** requested USD and USDT remain distinct; unsupported quote/product fails closed without silent substitution.
3. **Time semantics:** timezone-aware observation timestamp, missing/naive timestamp, malformed timestamp, future timestamp, and separate retrieval timestamp.
4. **Field semantics:** absent supply, absent max supply, absent volume, and provider-vs-derived FDV; ensure unknown values remain null.
5. **Numeric safety:** booleans, strings, NaN, infinity, negative values where invalid, overflow, and malformed rows.
6. **Coverage and ranking:** pagination/universe limits, stable deterministic ordering, quote currency, and provider-specific market coverage.
7. **Rate limits and failures:** HTTP 429, other HTTP errors, timeout, network failure, invalid JSON, bounded response size, and sanitized errors.
8. **Cache behavior:** fresh cache, expired cache, stale fallback, stale-cache metadata, and ensuring stale data is not analysis-eligible.
9. **Provenance:** primary success, fallback success, cache response, and total failure must identify the actual source path and timestamps.

Offline mocked tests establish deterministic adapter behavior only. They do not establish live-provider availability or deployed service behavior.

## Decision

1. Preserve the established Coinbase-public-data-first preference where Coinbase can satisfy the requested data contract.
2. Do not claim Coinbase candles can provide a complete market-cap-ranked screening universe. They cannot supply the current screening schema by themselves.
3. Keep provider-specific adapters and provenance visible in responses. Never silently substitute quote assets, symbols, timestamps, or providers.
4. Before changing defaults, write and test an adapter contract covering response schema, stable asset identity, quote currency, timestamp units/time zone, pagination/coverage, rate limits, bounded response sizes, cache/stale semantics, and sanitized provider failures.
5. Use offline mocked tests for all adapter paths. Live-provider smoke tests, if later performed, must be explicitly labelled and must not be treated as proof of production reliability.
6. No paid credentials or card-required services should be introduced without explicit review. Prefer public endpoints and a $0-first design.
7. Keep all market access read-only: no account authentication, order placement, trade execution, wallet control, private keys, or fund movement.

## Recommended migration sequence

- **Phase A — candle integrity:** complete the Coinbase USD/USDT quote-market regression PR; verify CI; do not merge automatically.
- **Phase B — screening contract:** document the exact fields and ranking semantics used by the screening endpoint, including which values are provider-reported versus derived.
- **Phase C — provider feasibility:** compare public Coinbase endpoints with the required screening contract. If Coinbase cannot provide a required field or universe ranking, record the gap rather than fabricating it.
- **Phase D — candidate adapter:** add a separately tested adapter behind an explicit configuration/feature flag; preserve the current provider and clear provenance until the alternative is validated.
- **Phase E — review:** compare coverage, rate limits, freshness, failure behavior, and $0 constraints. Keep changes in a PR. Do not change Render settings or deploy without explicit authorization.

## Important limits

This document is a source-code inventory and architecture decision, not a claim that provider availability, live response quality, or deployed behavior has been verified. It does not authorize a production provider switch.
