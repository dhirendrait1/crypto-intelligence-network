# Coinbase candle-request URL and query integrity

CIN constructs Coinbase candle requests only after canonical symbol parsing and exact public product-catalogue verification.

## Request construction contract

- The product identifier is the canonical Coinbase product ID returned by the symbol-mapping helper.
- The product identifier is URL-path encoded with no additional safe characters before insertion into the fixed Coinbase candles endpoint template.
- Query parameters are built from a fixed mapping containing exactly `granularity`, `start`, and `end`; no caller-provided query string or arbitrary parameter is appended.
- Granularity is selected from CIN's fixed interval-to-provider-seconds mapping.
- Start and end are generated from UTC-aware datetimes, serialized with an explicit UTC offset, then encoded by the standard query encoder.
- The requested window is aligned to the selected candle duration. Pagination boundaries remain bounded by the configured page size and page-count limit.
- The product catalogue request is performed first. A missing, ambiguous, mismatched, disabled, or unknown-status product prevents candle URL construction/request.

## Regression coverage

A deterministic clock fixture verifies the exact product path, HTTPS host, absence of fragments, exact query-key set, granularity value, and UTC start/end serialization for a fixed BTC-USD request. The test captures the actual URL passed to the request adapter rather than testing URL helpers in isolation.

## Scope and limitations

This is an offline request-construction contract test. It does not verify Coinbase's live server behavior, network availability, authentication requirements, or production readiness. The adapter remains read-only public market-data retrieval; no order, wallet, or funds operations are introduced.

## Coinbase HTTP status classification

Coinbase HTTP error responses are classified separately from transport failures and malformed successful bodies. Status handling is fail-closed and does not initiate another provider attempt:

- HTTP 418 and 429 are reported as rate limiting with a retry-later response (503).
- HTTP 401 and 403 are terminal access-denied responses (502).
- HTTP 404 and 410 are terminal endpoint/market-unavailable responses (502).
- HTTP 5xx responses are reported as temporary provider unavailability (503).
- Other HTTP 4xx responses and unexpected non-error statuses are rejected as provider/request failures (502).
- URL/network failures remain transport failures; malformed HTTP 200 bodies remain malformed-provider failures.

These classifications affect the API response only. They do not broaden the existing Binance-to-Kraken-to-Coinbase fallback policy: once Coinbase is reached, no further provider fan-out is possible or attempted. No HTTP status is treated as permission to substitute a different data source. Offline tests cover representative status classes; they do not establish live Coinbase behavior.

## Coinbase transport failure classification

Coinbase transport failures are separated from HTTP status responses and successful-response data failures:

- Socket/request timeouts are classified as timeouts.
- DNS lookup failures are classified separately from connection failures.
- TLS handshake/transport failures are identified independently.
- Connection refusal, reset, and interrupted writes are grouped as connection failures.
- Other operating-system transport errors are reported as generic network failures.
- These failures return a temporary-unavailability response (503); after Coinbase is reached, no further provider fallback is attempted.
- Invalid, empty, unsupported, or malformed provider data is not re-labelled as a transport outage; it fails closed as a provider/data response error (502).

The HTTP client retains its bounded 15-second request timeout. Offline exception-classification tests do not measure real network latency, DNS behavior, TLS trust, or Coinbase uptime.
