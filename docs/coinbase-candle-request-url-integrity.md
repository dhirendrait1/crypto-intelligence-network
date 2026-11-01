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


## Coinbase retry and repeated-request policy

The Coinbase adapter intentionally performs **zero automatic retries**:

- The shared HTTP request helper makes one urlopen call per request, with a 15-second timeout.
- The product catalogue is fetched once per Coinbase snapshot, followed by each required candle page exactly once.
- HTTP 418/429, HTTP 5xx, and transport failures are surfaced as failures; a retry-later API classification is guidance to the caller, not an internal retry instruction.
- A failed or malformed candle page aborts the complete Coinbase snapshot. Previously received page rows are not returned as a partial snapshot, and the failed page is not replayed.
- No retry loop, exponential backoff, or automatic repeat of a Coinbase catalogue/candle request is introduced. This avoids rate-limit amplification and avoids combining pages fetched at different times after a retry.

Offline regression tests verify one HTTP attempt for a transport failure, one attempt for HTTP 429, and abort-on-failure without replay of a later pagination page. These tests do not establish live provider consistency or guarantee that a subsequent client-initiated request will observe the same exchange snapshot.


## Coinbase retrieval-window consistency

CIN captures its UTC request-window anchor once, after local symbol/interval validation and **before** the product-catalogue request. The catalogue check and all candle-page requests therefore belong to one fixed, granularity-aligned requested time window; time spent waiting for catalogue or page responses cannot move the end boundary or cause later pages to use a newly calculated window.

This is a **best-effort retrieval window, not an atomic exchange snapshot**. Coinbase's public catalogue and candle endpoints do not provide a shared snapshot token in this adapter. Product status or candle values may change while separate HTTP requests are in flight, and the adapter cannot prove all returned pages represent one exchange-state instant. CIN therefore keeps the fixed window, validates page bounds and duplicate boundaries, performs no automatic retries, and fails the whole result on a failed or malformed page. Consumers must not interpret the output as a transactionally consistent exchange snapshot.

An offline regression test verifies that the time anchor is captured before catalogue I/O and that both pages use contiguous boundaries derived from that single anchor. It does not simulate or prove atomicity at Coinbase.


## Coinbase in-progress candle handling

The Coinbase candle request may cover the current granularity bucket when the request is made between bucket boundaries. The adapter now treats the bucket whose open time equals the request-window's current aligned boundary as **in progress**, not finalized: it validates the provider row and page placement as usual, but excludes that current bucket from the canonical completed-candle result. The most recent returned Coinbase candle therefore has a close time that represents an elapsed interval, rather than assigning a completed close boundary to a still-forming candle.

At an exact interval boundary, the newly opening bucket is not requested as part of the completed history. This policy is intentionally limited to Coinbase normalization in this audit; it does not claim that every provider exposes or finalizes candles identically. CIN's canonical candle response remains unchanged and does not add a provider-specific completion flag. Consumers receive completed Coinbase candles only, avoiding a schema change that could mislead existing technical-analysis consumers.

Offline regression tests cover a mid-interval response containing both a completed candle and the current in-progress candle, and an exact-boundary request. They do not verify Coinbase's live publication timing or guarantee that the exchange never revises a previously closed candle.


## Coinbase OHLCV numeric integrity and precision

The Coinbase adapter accepts provider JSON scalar fields and normalizes OHLCV values to the existing canonical Python float schema. Before a row is returned, the shared candle validator requires:

- finite, strictly positive open/high/low/close prices;
- finite, non-negative volume (zero-volume candles are permitted);
- high at least as large as both open and close, low no greater than either, and high not below low;
- valid integer open/close timestamps within the supported timestamp range.

Booleans, nulls, arrays, objects, malformed numeric strings, NaN, positive/negative infinity, float-overflow values, non-positive prices, negative volume, and impossible OHLC relationships fail closed. A malformed row aborts the Coinbase snapshot; CIN does not silently drop it and return a partial result.

**Precision limitation:** the canonical API currently represents prices and volume as binary floating-point values. Coinbase decimal strings with more significant digits than the float representation can preserve may be rounded during normalization. The audit adds regression coverage for this conversion and does not claim arbitrary-precision decimal fidelity. Changing the public numeric schema to decimal strings or scaled integers would require a separate compatibility audit of downstream analytics and API consumers; no such schema change is included here.

Offline tests validate representative malformed and high-precision inputs. They do not establish exchange-side decimal semantics or market-specific tick/lot increments, which require authoritative instrument metadata and a separate audit.


## Coinbase interval-grid integrity

Coinbase request-window starts and page boundaries are constructed on the requested granularity grid, but request bounds alone do not prove that each returned candle open belongs to that grid. The adapter now independently requires every returned candle timestamp (including any provider-supplied pre-window context row) to be divisible by the requested granularity in Unix UTC seconds. A misaligned row fails the entire snapshot as a malformed provider response; CIN does not round, shift, or silently discard it.

The check is epoch-based and applies to the fixed-duration Coinbase granularities supported by this adapter. It is distinct from timestamp-unit validation, page ordering, duplicate-boundary reconciliation, and current-candle exclusion. Regression tests cover a timestamp that is valid and inside the page window but off the interval grid, plus valid minute/hour-aligned opens. Calendar-based intervals are not represented by this fixed-second Coinbase granularity mapping.


## Step 189 — Coinbase interval continuity and missing buckets

The Coinbase adapter may return fewer candle rows than the number of interval buckets in the requested time span. This audit distinguishes **internal continuity** (missing expected opens between two returned candles) from leading/trailing request-window shortfalls. The existing `timeline_integrity` metadata reports internal gaps using the requested interval duration and records each gap's previous open, next observed open, expected next open, and missing-interval count.

For Coinbase, a gap is an observation about absent candle rows, not proof of provider feed loss. Coinbase historical candle data may omit intervals with no trades; the response therefore labels this interpretation as `missing_intervals_may_indicate_no_trades` when a Coinbase gap is present. A consumer must not treat an absent row as a zero-volume candle or infer a price for it.

The audit adds Coinbase-focused offline regression coverage for:
- fully contiguous returned hourly candles (zero internal gaps);
- one missing interval between observed candles;
- multiple missing intervals across more than one discontinuity;
- sparse raw Coinbase adapter output remaining sparse while the timeline report identifies the missing bucket.

**No synthetic data is created.** The adapter preserves provider-returned candles; the timeline report is metadata only. It does not create rows, interpolate OHLC values, set volume to zero, or repair the provider response. The scope is limited to gaps between returned candles; leading/trailing window coverage remains separately described by `historical_window_integrity` and is not re-audited here.

The shared timeline helper is already used by the market-candles endpoint, so this step adds Coinbase-specific regression evidence and documentation rather than introducing a second competing gap detector or changing the canonical candle schema. These offline tests do not establish why Coinbase omitted a particular interval or prove live feed completeness.



## Step 190 — Coinbase candle row schema cardinality

Coinbase Exchange candle rows use a six-element positional schema: `[time, low, high, open, close, volume]`. The adapter previously rejected rows with fewer than six values but accepted rows with additional values, silently ignoring the extras during OHLCV normalization. That permissive behavior could conceal an unexpected provider response shape or an upstream schema change.

The adapter now requires every row to be a list containing **exactly six fields** before timestamp chronology validation or OHLCV normalization. Rows with missing or extra fields, and tuple/object alternatives, fail closed as malformed successful provider data. CIN does not guess at extra columns, shift positions, or ignore unknown fields.

Offline regression coverage includes the exact six-field contract, every shorter row length, an extra seventh field, and a non-list row with six values. Existing newest-first chronology validation and explicit oldest-first conversion remain unchanged. This is a response-shape check only; it does not claim that the provider's field values are semantically correct beyond the separate timestamp and OHLCV validators.

No canonical candle schema, provider fallback policy, synthetic data behavior, or read-only operating boundary is changed.



## Step 191 — Coinbase candle field types and timestamp representation

The Coinbase candle adapter now enforces the documented raw field types before numeric normalization:

- The timestamp field must be a JSON integer representing Unix seconds. Boolean, floating-point, and string timestamps are rejected rather than coerced, even when their textual or numeric value looks integral.
- Each OHLCV field must be a scalar string, integer, or floating-point number. Boolean values and structured values such as null, arrays, objects, and tuples are rejected before conversion.
- Existing finite-number, positive-price, non-negative-volume, and OHLC relationship validation remains responsible for semantic numeric validity after scalar type checks.

This is deliberately provider-specific. It does not change timestamp-unit bounds, interval alignment, row cardinality, page chronology, canonical timestamp units, or the public candle schema. Numeric OHLCV strings remain accepted because Coinbase returns decimal values in string form in its documented candle response.

Offline regression tests cover rejected string/float timestamps, accepted integer timestamps with mixed documented numeric OHLCV scalar forms, booleans in every OHLCV position (including volume), and structured OHLCV values. These tests establish local adapter behavior, not live-provider behavior or future API compatibility.

No data is repaired or synthesized. Malformed successful provider rows fail closed. CIN remains read-only; no order execution, wallet access, merge, deployment, or production activation is introduced.
