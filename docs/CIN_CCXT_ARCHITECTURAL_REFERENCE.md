# CCXT public market-data architectural reference

Status: proposed architecture, not an implementation or deployment claim. This reference supplements CIN's master roadmap and existing architecture. It does not authorize or enable a connector, change production services, or prove provider availability.

## Permanent boundary

CIN remains a public-data research, monitoring and alerting system. No trade execution, order placement, routing, modification or cancellation; no exchange account linkage, wallet connection, private keys, seed phrases, custody, balance access or fund transfers. Public trades and public order-book observations are permitted for research. No API credentials are required for the proposed public-data proof of concept. CCXT contains private and trading methods: any future adapter must expose a narrow allowlist of public operations and must not expose the library's general exchange object or arbitrary methods to application callers.

## Architectural fit

Public exchange APIs → optional CCXT adapter → CIN normalization and validation → provenance and storage → research engines → API and dashboard.

CCXT is a client library, not an exchange, a market-data source, a prediction engine, or a substitute for CIN's quality gates. Each provider must be separately evaluated for public access, region, capability, market identity, rate limits, terms, timestamp quality and cost. Binance HTTP 451 remains a provider restriction; CCXT is not a workaround.

## Capabilities to evaluate

1. Unified interface for eligible public exchange adapters, with independently replaceable connectors.
2. Public ticker, price, volume, candles and order-book snapshots, subject to exchange support.
3. Bounded fallback for validated, equivalent instruments; show the actual source and failure reason.
4. Rate limits, request budgets, caching, bounded retries with backoff and circuit breaking, including controls across workers. CCXT's limiter is per exchange instance and is not a distributed budget.
5. Public WebSocket subscriptions where supported, with reconnect, heartbeat, bounded memory, stale detection and gap recovery. A continuous animation must not imply an update when no verified new event is received.
6. Derivatives research where a provider supplies eligible public data: identify venue, underlying, quote/settlement currencies, contract type, units, timestamp and funding interval. Unknown values remain unavailable.
7. Market metadata, symbols, market status and exact identity checks, including spot versus perpetual, expiry and contract specification.
8. Unified failure categories for timeout, provider unavailability, throttling, unsupported market, malformed data and regional restrictions, without leaking secrets.
9. Historical candles and public trades within each provider's limits; report retention, gaps, pagination and coverage. CCXT does not guarantee complete history.
10. Public bid/ask depth, spread and liquidity observations, labeling venue, depth, units and timing; do not label order-book imbalance as verified buy/sell pressure.
11. Cross-exchange price, spread and volume comparisons only for validated comparable instruments; label units and non-simultaneous observations.
12. Provider health observations, latency, freshness and reliability with explicit unknown and unavailable states.
13. Normalized schemas with raw-provider identifiers, retrieval time, provider observation time and uncertainty preserved.
14. Bounded asynchronous requests and concurrency, cancellation, timeouts and resource management.
15. Modular adapter configuration, explicit public-method allowlists, tests, version pinning, dependency review and documented rollback.

## Proposed implementation order

1. Define adapter contracts, public-only boundary and offline tests.
2. Evaluate Kraken public market metadata, ticker and candles beside the existing implementation; do not replace the working adapter before validation.
3. Apply identity, schema, timestamp, chronology, numerical integrity, freshness and provenance gates to each result.
4. Add and test an eligible second provider and bounded fallback. Never equate USD with USDT or spot with derivatives.
5. Evaluate WebSocket streaming only after the snapshot path works; account for availability and free-tier resource budgets.
6. Evaluate derivatives, public liquidity and cross-exchange comparisons with explicit units and contract equivalence.
7. Add provider health reporting, operational controls, release evidence and recovery procedures.

## Acceptance evidence

Use mocked contract and failure tests plus separately recorded live checks on the test service before deployment. Verify correct symbol and market type, valid closed candles, timestamps and missing-data handling, appropriate retries and rate budgets, safe provider fallback and truthful source labels. Test streaming disconnect, stale data and reconnect behavior before enabling it. Ensure no private credentials or private/trading methods are reachable. Keep missing, stale, failed or unsupported observations out of eligible research. Assess dependency and free-tier resource impact before activation.

CCXT does not provide CIN's news, social sentiment, fundamental evidence or reliable forecasts by itself. Existing mandatory shortlist evidence and the rule against fabricated results remain unchanged.

References: [CCXT repository](https://github.com/ccxt/ccxt), [CCXT manual](https://github.com/ccxt/ccxt/wiki/Manual), [CCXT Pro manual](https://github.com/ccxt/ccxt/wiki/ccxt.pro.manual).
