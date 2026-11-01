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
