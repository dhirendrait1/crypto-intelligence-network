# CIN coin-screening data contract

**Purpose:** define the evidence contract for coin screening before any provider migration. This is not a production behavior change.

## Required response fields and semantics

| Field | Meaning | Validation / interpretation |
|---|---|---|
| `id` | Provider asset identity | Required non-empty provider ID; symbols alone are not unique identities. |
| `symbol`, `name` | Display identity | Treat as labels, not canonical identifiers. Preserve provider identity and avoid merging assets solely by ticker. |
| `current_price` | Price in requested quote currency | Finite, non-negative numeric value; quote currency must be explicit in metadata. A missing value remains missing. |
| `market_cap` | Provider-reported market capitalization in quote currency | Finite and non-negative; preserve null when unavailable. Never derive a rank from a missing cap as if it were zero. |
| `total_volume` | Provider-reported 24-hour volume in quote currency | Finite and non-negative; timestamp/window semantics must be recorded. |
| `circulating_supply`, `total_supply`, `max_supply` | Provider supply fields | Finite and non-negative; zero/unknown max supply is not a usable denominator for FDV. |
| `fully_diluted_valuation` | Provider-reported FDV or explicitly derived price × max supply | Distinguish provider-reported from derived. Derived only when both inputs are valid; never imply the result is provider-observed. |
| `price_change_percentage_24h` | Provider-reported 24-hour change | Finite signed number; document provider window and update time. |
| `last_updated` | Provider's market-data update time | Parse timezone-aware timestamps only; invalid/missing timestamp means freshness unknown, not fresh. |
| `_cin_provider` | Actual upstream provider | Must reflect the provider that supplied the row, not a preferred/default provider. |
| `_cin_quote_currency` | Quote currency used for the numeric values | Must match the requested currency and provider response; never convert a quote asset by relabelling. |
| `_cin_retrieved_at` | CIN retrieval time | Separate from provider market update time; do not use retrieval time as a substitute for price timestamp. |

## Ranking rules

1. Primary ranking is descending provider-reported market cap only when market cap is a valid finite non-negative number.
2. Rows with missing market cap must not be presented as if they have a valid market-cap rank. If included, label them as unranked or place them after ranked rows with an explicit reason.
3. Do not synthesize market cap from price × supply unless a future contract explicitly introduces a separately labelled derived metric and validates the supply basis.
4. Do not infer a complete market universe from a list of tradable Coinbase products or candles. A product list is an exchange-specific subset, not global market-cap coverage.
5. Deduplicate only by stable provider asset identity. Never deduplicate by symbol alone.
6. Keep quote currency, source provider, provider update time, retrieval time, and cache status visible in API metadata.
7. On provider fallback, preserve primary and fallback error attribution in sanitized metadata. Do not silently mask a fallback as the primary provider.

## Provider feasibility decision

Coinbase public spot candles provide OHLCV for individual products and supported granularities; that is not equivalent to the market screening contract above. A Coinbase product-list endpoint, even if public, would not by itself establish global market cap, circulating supply, or market-cap rank. Therefore, do not replace the existing screening provider with candle data or claim Coinbase-only global screening until every required field and coverage limitation is independently resolved.

## Test gate before any adapter or default change

- Mock provider payloads for missing/duplicate IDs, symbol collisions, malformed types, booleans masquerading as numbers, NaN/infinity, negative fields, missing quote currency, stale/invalid timestamps, and partial supply/FDV inputs.
- Assert market-cap ranking and handling of unranked rows.
- Assert provider and quote provenance across primary, fallback, cache, and stale-cache paths.
- Assert response-size bounds, timeouts, rate-limit failures, and sanitized error metadata.
- Run offline tests in CI; do not call live providers from unit tests.
- No paid API, card-required service, secret, account endpoint, trade execution, wallet control, or fund movement is introduced by this contract.

## Current implementation notes

The current module uses CoinGecko market-cap-desc markets data and CoinPaprika ticker fallback. It maps provider values into a common row schema and adds provider/quote labels. These labels and normalized fields are useful, but provider-specific freshness, ranking completeness, and whether FDV is provider-reported or derived must remain explicit. This contract should guide a later adapter review; it does not authorize a provider switch.
