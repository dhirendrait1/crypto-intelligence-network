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
