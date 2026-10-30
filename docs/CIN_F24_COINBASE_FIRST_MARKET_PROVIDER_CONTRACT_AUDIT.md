# F-24 — Coinbase-First Market Provider Contract Audit

**Status: Partial — provider mismatch identified; live market panel intentionally blocked**  
**Branch:** `test/cin-step23-sqlite-persistence-reliability`  
**Scope:** Read-only public market data only. No account access, credentials, order placement, trading, wallet control, or fund movement.

## 1. Audit outcome

The current checked-in market-candle implementation is not Coinbase-first:

- `cin_public_market_candles_api.py` declares Binance public klines as its primary provider and Kraken public OHLC as fallback.
- `docs/CIN_PUBLIC_MARKET_CANDLES.md` describes the Binance/Kraken path.
- `cin_derivatives_market_data_api.py` uses Binance USDⓈ-M public futures endpoints.
- The repository tree contains no Coinbase-specific provider adapter or Coinbase market-data contract test suite.

This conflicts with the project data preference: Coinbase public market data first and CoinGecko excluded unless the project owner explicitly changes that preference. The existing Binance/Kraken path is not silently re-labelled as Coinbase.

## 2. Dashboard integration decision

**Do not connect `/market-candles`, `/technical-analysis/market`, derivatives, screening, or any cached provider output to the dashboard as Coinbase data.** A provider-neutral UI is not sufficient when the actual source precedence and symbol/interval semantics are not verified.

The current frontend therefore remains an explicit preview with no live prices. This is intentional data-integrity protection, not a missing UI placeholder to work around.

## 3. Required Coinbase-first contract

Before market panels can be enabled, a dedicated read-only adapter and tests must establish:

1. Public, unauthenticated endpoint selection and documented request limits.
2. Product-ID mapping and explicit rejection/normalization rules (for example, BTC-USD versus BTCUSDT); never assume quote currencies are interchangeable.
3. Supported candle granularities, maximum row limits, pagination behavior, and UTC timestamp interpretation.
4. OHLCV numeric validation, candle ordering, duplicate handling, missing intervals, and forming-versus-closed candle semantics.
5. Provenance fields: provider name, endpoint family, product ID, granularity, retrieval timestamp, source candle timestamps, and fallback reason if any.
6. Error taxonomy for timeout, rate limiting, unsupported product/granularity, malformed response, and provider outage.
7. A deterministic provider-selection rule: Coinbase first; any secondary source requires an explicit documented fallback policy and must never be presented as Coinbase-origin data.
8. Offline fixtures and tests for success, empty response, malformed rows, non-finite numbers, stale data, pagination, duplicate timestamps, and provider failure.
9. Contract compatibility review before API route registration or frontend wiring.

## 4. Acceptance gates

- **Gate A — adapter:** Coinbase public candle adapter and typed normalized model implemented.
- **Gate B — tests:** deterministic offline tests pass, including provenance and negative cases.
- **Gate C — API:** read-only route exposes truthful provider and timestamp metadata; no credential or execution surface.
- **Gate D — frontend:** market panel consumes only the verified response contract and visibly distinguishes fresh, stale, partial, conflicting, unavailable, and error states.
- **Gate E — live smoke test:** limited read-only public request validates endpoint behavior; record date, product, granularity, returned source, and limitations. CI fixtures alone do not satisfy this gate.

## 5. Explicit exclusions

No exchange account authentication, private API keys, order endpoints, order execution, wallet access, trade routing, paid data services, or production deployment are part of F-24.

## 6. Current disposition

F-24 is **not complete**. The audit has established the provider mismatch and prevented unsafe dashboard wiring. The next implementation increment is Gate A: a Coinbase public-data adapter with fixture-driven tests, after confirming current Coinbase public API contract details. No existing Binance/Kraken route has been modified by this audit.


## 7. Gate A implementation increment (2026-10-31)

Added `cin_coinbase_public_market_data.py` as a separate, bounded Coinbase Exchange public-candle adapter and `tests/test_cin_coinbase_public_market_data.py` for offline contract tests.

The adapter:
- Uses the fixed public Coinbase Exchange host and GET-only candle path; no API key or account access.
- Requires an explicit USD-quoted product ID (for example `BTC-USD`); it rejects `BTC-USDT` rather than silently substituting a USD market.
- Allows only documented candle granularities: 1m, 5m, 15m, 1h, 6h and 1d.
- Enforces a maximum 300-candle time window per request and a bounded response body.
- Normalizes Coinbase's `[time, low, high, open, close, volume]` row shape into CIN OHLCV with UTC millisecond open/close times.
- Filters malformed/non-finite/impossible rows, sorts chronologically, and de-duplicates identical timestamps.

**Gate A status: implemented in an isolated adapter; awaiting CI evidence and live read-only smoke validation.** It is not registered as a production API route and is not connected to the dashboard. The existing Binance/Kraken route is unchanged; no claim is made that the current dashboard is Coinbase-powered.


### Gate A/B verification evidence

- The storage-boundary workflow now compiles the adapter and runs its dedicated offline test module on every push to this work branch.
- GitHub Actions run [#41146066687](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/41146066687) completed successfully.
- All 9 Coinbase adapter contract tests passed, including fixed-host request construction, USD-only product identity, unsupported granularity, 300-candle bound, timestamp validation, response-shape validation, OHLCV normalization, malformed-row rejection, chronological sorting and duplicate timestamp handling.
- The existing storage-boundary regression tests also passed in the same workflow.

**Gate A: implemented and CI-verified. Gate B: initial offline adapter contract suite implemented and CI-verified.** This is not a live provider smoke test and does not yet register or expose the adapter through the production API.


### Gate C — isolated read-only API contract (2026-10-31)

Added:
- `cin_coinbase_market_data_api.py` — FastAPI router exposing `GET /coinbase/market-candles`.
- `tests/test_cin_coinbase_market_data_api.py` — API contract tests.
- CI now compiles the API module and runs both adapter and API test suites.

The route requires explicit Unix-second `start` and `end` bounds, an explicit Coinbase product ID, and a supported granularity. Its response carries provider identity, USD quote identity, retrieval time, candle timestamps, closed/forming state, freshness metadata, and limitations. Provider exceptions are not exposed to clients.

GitHub Actions [run #41146284133](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/41146284133) passed. The Coinbase adapter tests and API contract tests passed, together with the existing storage-boundary regression suite.

**Gate C status: isolated router and contract tests implemented and CI-verified; production application registration remains blocked.** The audited feature branch does not contain an independently maintained FastAPI application entrypoint/router registry (the Render deployment app is packaged separately in the scaffold archive). This route has therefore not been mounted into the running service or exposed publicly. No archive, Render service, or deployment was changed.

F-24 remains Partial. Remaining work includes safe integration into the actual deployment application source, API-level live read-only smoke validation, and dashboard wiring only after the deployed contract is verified.


### Gate C — Render build-time router registration verified (2026-10-31)

The deployment path has now been traced end-to-end:
- `render.yaml` extracts `cin_step203_scaffold_fixed.zip`, runs `patch_cin_metadata_fixed.py`, installs `cin/requirements.txt`, and starts `uvicorn app.main:app --app-dir cin`.
- The patch script now copies the Coinbase adapter and API router into the packaged `cin/app` directory and registers the router on the FastAPI application.
- The storage-validation workflow installs the same packaged runtime requirements, runs the patch script against an extracted archive, imports `app.main`, and asserts that `/coinbase/market-candles` appears in the mounted application routes.

Verification:
- [Storage validation #41146868606](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/41146868606) — success.
- [Storage validation #41146874005](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/41146874005) — success.
- [Frontend CI #41146873995](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/41146873995) — success.

**Gate C status: build-time route registration and packaged-app import verified in CI.** This does not mean the Render service has been deployed with the change. No deployment, Render configuration, or live service was modified. Live public Coinbase validation remains pending.
