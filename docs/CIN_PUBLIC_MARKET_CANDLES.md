# CIN Public Market Candles and Market-Backed Technical Analysis

These read-only endpoints use public exchange market-data endpoints. Provider selection may fall back from Binance to Kraken and then Coinbase for eligible pairs/timeframes. They do not require API credentials and do not access accounts or place orders.

## 1. Retrieve timestamped candles

`GET /market-candles?symbol=BTCUSDT&interval=1h&limit=100`

- `symbol`: public market pair such as `BTCUSDT`
- `interval`: supported Binance kline interval (for example `15m`, `1h`, `4h`, `1d`)
- `limit`: 5–500 candles
- Binance Spot REST klines supports up to 1,000 rows per request; CIN's public route intentionally caps requests at 500. The adapter independently rejects non-integer, boolean, non-positive, and over-1,000 request limits before making a provider call. With no `startTime` or `endTime`, Binance returns the most recent rows in chronological order; CIN relies on that bounded latest-window behavior and reports shortfalls rather than paging or fabricating history.
- Response includes OHLCV, open/close timestamps in milliseconds and UTC ISO format, source, retrieval time, and limitations. The `data_quality` summary reports invalid candle rejection, completed versus forming rows, stale completed data, and zero-volume rows for review; it never repairs or synthesizes provider candles. It also validates the supplied row order as received; it does not silently sort an out-of-order provider response before reporting quality. A zero-volume candle is flagged for review, not automatically treated as invalid.
- `coverage` compares the number of returned rows with the requested limit and reports `complete` or `partial`, the shortfall, returned-row ratio, a warning for short responses, and first/last returned candle opens. `complete` means the requested row count was met; it does not mean the timeline has no gaps or that the provider feed is healthy. A `partial` count is not proof of feed loss: inspect `timeline_integrity` and provider-specific omission semantics separately. Providers may return fewer rows because of listing history, provider retention, or invalid source rows; CIN reports the shortfall rather than padding or synthesizing candles.

## 2. Run technical analysis from public candles

`GET /technical-analysis/market?symbol=BTCUSDT&interval=1h&limit=100`

This fetches public candles and passes OHLC values into CIN's existing deterministic analysis engine (market structure, RSI, MACD, ATR, swing reference levels, and illustrative ATR scenarios). The response includes source, symbol, timeframe, retrieval time, and first/last candle times.

## Reliability and safety notes

- Data comes from the selected public exchange provider (Binance, Kraken, or eligible Coinbase fallback) and is not independently audited by CIN. Kraken OHLC responses must contain exactly one market-data result key (excluding the pagination cursor); ambiguous multi-market responses fail closed instead of selecting an arbitrary pair. Before Kraken OHLC is requested, CIN resolves the requested base/quote through the public AssetPairs catalogue, checks the returned altname and websocket pair name, requests the resolved altname, and verifies the OHLC result key against that exact market record. Unresolved, mismatched, or ambiguous market identities fail closed. Kraken REST OHLC is limited to 720 time steps per response and always includes the current not-yet-committed candle. CIN's public request limit is at most 500, so no OHLC pagination is required; responses over 720 rows fail closed. The current forming row may remain in returned data, but completed-candle freshness excludes it until its close time has passed; coverage reports returned rows separately from completed-candle freshness.
- The most recent candle may still be forming. Use timestamped snapshots and account for that when comparing signals. Responses classify completed-candle freshness as `fresh`, `stale`, or `no_completed_candle` using a two-interval age threshold; `is_stale` is `true`, `false`, or `null` respectively. A stale snapshot is explicitly labelled and must not be presented as live. Candles whose open timestamp is later than retrieval time fail closed with HTTP 502; a future-dated candle is not treated as merely forming.
- Before a public candle snapshot is returned, every row's provider tag, source label, and source endpoint are checked against the single selected provider. Mixed row provenance, a provider/endpoint mismatch, or a fallback reason inconsistent with the source label fails closed with a sanitized HTTP 502; CIN does not present a mixed-provider snapshot as one exchange feed.
- Binance HTTP 451 or a transient transport failure (connection error/timeout) may trigger Kraken and then Coinbase public-data fallback; the response labels the actual provider and fallback reason. HTTP 418/429 rate limits at Binance or Kraken fail closed with retryable HTTP 503 responses and do not fan out to another provider. Coinbase rate limits also return HTTP 503; no further provider is attempted. Malformed or oversized successful primary-provider payloads fail closed with a sanitized HTTP 502 and do not trigger fallback; non-451 HTTP errors fail closed; unavailable fallbacks return a retryable 503 rather than stale data. Endpoint-level timeline and technical-analysis integrity failures also return sanitized HTTP 502 responses without exposing internal validation details.
- Coinbase fallback is restricted to USD-quoted pairs (for example, `BTCUSD`). A USDT request is not substituted with a USD product; quote assets are not interchangeable.
- Coinbase candle history is fetched in adjacent UTC-granularity-aligned windows of at most 300 requested intervals per call. Page boundaries are contiguous and timestamp-keyed collection deduplicates identical repeated boundary rows; if the same open timestamp appears with conflicting row values, the provider snapshot fails closed instead of silently overwriting one version. Any individual response exceeding 300 rows fails closed. Coinbase documents that a response may include candles preceding the declared `start`; CIN filters returned opens to its requested UTC window before collection. Historical data may omit intervals with no ticks, so missing Coinbase candles are not automatically evidence of feed loss. Regression tests cover multi-window retrieval, out-of-window row rejection, and oversized page rejection. Coinbase candle rows are screened for finite positive OHLC values, non-negative finite volume, valid OHLC ranges, and whole-second timestamps within the supported datetime range; invalid rows are excluded. Before a snapshot is returned, the normalized sequence is checked again for valid OHLCV values, integer non-boolean timestamps, exact requested-timeframe candle duration (including calendar-month duration), duplicate open timestamps, and overlapping candle time ranges; ambiguous snapshots fail closed with HTTP 502. Valid rows are selected into the requested latest-candle window only after OHLCV validation, so an invalid newest row does not crowd out an older valid row.
- Before returning normalized provider snapshots, CIN checks candle-open alignment against explicit provider identities: Binance weekly candles use Monday 00:00 UTC, while Kraken weekly candles use Thursday 00:00 UTC; Coinbase weekly/monthly alignment is unsupported. Monthly candles are checked against the first day of the month for Binance. Fixed-duration intraday/daily intervals are checked against UTC boundaries. Binance 3-day candles currently use an epoch-based 72-hour check; the provider documentation lists the interval but does not specify its anchor, so this convention remains unverified and must not be interpreted as independently confirmed. Unsupported provider/interval combinations and unknown providers fail closed with HTTP 502.
- Both `/market-candles` and `/technical-analysis/market` include `timeline_integrity`, reporting internal gaps between returned candle opens and the count of missing expected intervals. The check does not infer gaps before the first or after the last returned candle, and it never synthesizes or interpolates candles. A gap does not establish why a provider omitted data; monthly intervals use calendar-month boundaries. The market-candles response also records the selected provider and a conservative gap interpretation: Kraken and Coinbase may omit intervals with no trades, so a gap from either provider is not proof of feed loss; for providers without an explicitly established rule, the cause remains unclassified.
- The offline `compare_provider_candles` diagnostic compares already-fetched snapshots for the same market: exact timestamp overlap, provider-specific missing timestamps, timeline gaps, OHLC discrepancy in basis points, and volume discrepancy in basis points. When `market_identity_by_provider` is supplied, it requires a complete base/quote asset identity for every provider and fails closed if identities differ (for example, BTC/USD versus BTC/USDT); without that explicit mapping, the report states that market identity was not verified. For Binance, Kraken, and Coinbase-labelled inputs, any present per-row `_provider` provenance tag must match the provider bucket; mismatches fail closed rather than allowing fallback data to be attributed to the wrong source. Timeline-gap counts use calendar-month stepping for `1M` and fixed interval stepping otherwise; off-grid timestamps fail closed. The standalone timeline helper rejects duplicate/overlapping opens, and provider comparisons validate each candle's exact timeframe duration plus known Binance/Kraken/Coinbase boundary conventions; arbitrary provider labels are not assigned a guessed weekly anchor. It does not fetch data, interpolate timestamps, choose a trusted provider, or independently verify symbol/quote identity.
- Unsupported symbols/intervals and invalid limits are rejected.
- Volume is returned as provider context but is not yet used in indicator calculations.
- No credentials, user accounts, order placement, or trade execution are involved.
- RSI/MACD/ATR and structure labels are descriptive analytical outputs, not guaranteed predictions or financial advice.


### Historical request-window integrity

The `historical_window_integrity` response compares returned candle opens with the provider-aligned rolling window implied by the requested interval count and retrieval time. It reports expected start/end opens, missing leading and trailing intervals, and rows outside the expected window. A partial edge window is a coverage observation, not proof of provider feed loss: Kraken and Coinbase may omit intervals with no trades. CIN never fills or synthesizes missing candles. Unsupported provider/timeframe boundary combinations fail validation rather than guessing an anchor.


### UTC boundary and provider timestamp validation

CIN normalizes provider timestamps to integer Unix milliseconds before shared processing: Binance supplies milliseconds, while Kraken and Coinbase supply seconds. Candle opens are validated against UTC interval boundaries, and close timestamps must equal the exact interval end (including calendar-month lengths). Weekly boundaries are provider-specific: Binance Monday 00:00 UTC and Kraken Thursday 00:00 UTC; Coinbase weekly candles are unsupported. Monthly candles are currently supported only for Binance. These rules are UTC-based and do not follow a client device's local timezone or daylight-saving transitions. Unsupported or misaligned rows are rejected rather than shifted.


### Fallback failure and partial-response contract

Provider failover is deliberately narrow. Binance HTTP 418/429 rate limits return a retryable service error without fan-out; other Binance HTTP errors fail closed, and malformed/empty successful payloads are not treated as transport outages. A successful but short candle response remains a short response: CIN does not pad it with fabricated rows or silently switch providers to reach the requested count. When Binance is unavailable through an eligible transport failure or HTTP 451, a partial Kraken snapshot remains explicitly labeled as Kraken fallback data; Coinbase is considered only if Kraken itself fails or cannot serve the requested market/timeframe. Quote assets are never substituted (for example, USDT is not mapped to USD). Regression tests cover these behaviors; test execution must be confirmed by exact-head CI before release.


### Malformed provider-row handling

A successful HTTP response is not considered a healthy candle snapshot merely because some rows can be parsed. Binance, Kraken, and Coinbase adapters reject a snapshot when any in-window candle row has an invalid structure, timestamp, or OHLCV value; malformed rows are not silently skipped to make the remaining response appear complete. Kraken/Coinbase no-trade interval omissions remain a distinct provider behavior and are still represented through timeline/coverage diagnostics. Coinbase rows outside the explicitly requested UTC window are filtered as out-of-window data before candle validation; this is not treated as a malformed in-window candle. Malformed successful provider payloads fail closed with a sanitized provider error and are not used to trigger another provider as a way to hide the defect. No rows are repaired, imputed, or synthesized.


### Coinbase page-boundary integrity

Each Coinbase response page is checked against its own UTC-granularity window. CIN permits the single immediately preceding candle that Coinbase may include at a page start, and permits the shared page-end boundary so an identical repeated candle can be deduplicated. Rows older than that one-candle allowance or later than the requested page end fail closed as a malformed pagination response. Identical repeated boundary rows are retained once; conflicting rows for the same open timestamp remain a hard integrity failure. This page-level check is separate from the overall requested-window filter and does not create or repair candles.


### Kraken response-envelope and cursor integrity

Kraken AssetPairs and OHLC responses must provide an object envelope with an explicitly present, empty-list `error` field. The OHLC `result` must contain exactly one resolved market key plus the `last` pagination cursor. The cursor must be a finite, non-negative integer Unix timestamp and must not precede the latest returned candle open. Missing, malformed, boolean, fractional, or stale cursors fail closed; CIN does not guess a cursor or retry with a different market key to conceal an invalid envelope. The cursor is validated as response metadata and is not used to fabricate additional candle rows.


### Kraken candle ordering and duplicate integrity

Kraken OHLC rows are checked in their original provider response order before the shared normalization stage. Open timestamps must be strictly increasing; duplicate or descending timestamps are malformed provider data and fail closed rather than being sorted into an apparently valid sequence. The pagination cursor is independently checked against the latest returned candle open. CIN does not deduplicate or reorder a malformed Kraken response to conceal provider-side chronology defects.


### Kraken UTC interval-boundary and forming-candle handling

Kraken candle opens are validated against the provider-specific UTC timeframe anchor at the adapter boundary, before rows enter shared normalization. The adapter verifies that the interval duration used to derive each close timestamp matches CIN's supported timeframe duration. Misaligned opens fail closed as malformed provider data. The current/incomplete candle returned by Kraken remains in the response when otherwise valid; freshness and quality metadata distinguish it from completed candles rather than silently dropping or rewriting it. Weekly candles use Kraken's Thursday 00:00 UTC anchor. No local-time or daylight-saving adjustment is applied.


### Kraken fallback error classification

A malformed successful Kraken response is a data-integrity failure, not provider unavailability. AssetPairs/OHLC envelope shape, explicit error-list contract, resolved market identity, OHLC result key, pagination cursor, row count, candle rows, chronology, and UTC timeframe alignment are validated as malformed-provider failures. Invalid JSON/Unicode and oversized successful response bodies are classified the same way. These failures return HTTP 502 and do not trigger Coinbase fallback. Network/transport failures remain transport failures; eligible Kraken HTTP errors retain the documented fallback behavior, while rate limits remain retryable HTTP 503 and do not fan out. An actual Kraken API error list or unsupported requested market/timeframe remains distinguishable from a malformed response and may be handled by the existing fallback policy.


### Coinbase fallback response classification

A successful Coinbase HTTP response with an invalid JSON/Unicode body, non-list payload, oversized page, conflicting duplicate boundary row, malformed candle row, or empty usable candle set is a provider data-integrity failure and returns sanitized HTTP 502. It is not reported as ordinary provider unavailability (HTTP 503). Transport failures and HTTP errors remain separately classified. Kraken AssetPairs responses that do not resolve exactly one requested market are likewise malformed successful responses and must not be hidden by Coinbase fallback.


### Cross-provider comparability and overlap reporting

The offline comparison does not label snapshots consistent when market identity has not been explicitly verified for every provider. Without a complete base-asset/quote-asset mapping, `consistency_status` is `market_identity_unverified`, even if candle values and timestamps happen to match. With verified identity, the comparison still requires exact candle-open timestamp overlap for every provider pair; it does not interpolate or shift provider-specific boundaries. Pairwise reports include the shared timestamp ratio (shared opens divided by the union of opens) and the exact shared UTC window, while provider summaries expose each snapshot's UTC start/end. Missing timestamps and coverage mismatches remain visible and prevent a clean consistency result. These diagnostics establish comparability conditions only; they do not identify a trusted provider or certify data correctness.


### Cross-provider historical-window equivalence

Cross-provider comparison reports each snapshot's first and last UTC candle opens, its coverage ratio against the union of observed opens, and separate leading-window, trailing-window, and internal missing-timestamp counts. Pairwise diagnostics distinguish candles present only before or after the shared overlap window from candles missing inside a provider's own observed window. Different retention horizons or partial historical windows are therefore visible as window mismatches rather than being mistaken for direct full-window equivalence. Numeric OHLCV deltas are calculated only at exact shared candle-open timestamps. Any missing union timestamps prevent a clean consistency result; no historical rows are backfilled, interpolated, or synthesized. Provider-specific no-trade omissions remain possible and are not automatically classified as feed failure.


### Cross-provider OHLCV value and unit integrity

The offline comparator validates finite, positive OHLC prices, internally consistent high/low ranges, finite non-negative volume, exact candle durations, provider provenance, and exact shared open timestamps before calculating discrepancies. OHLC price deltas are symmetric basis-point diagnostics; unusually large values are reported but do not identify which provider is wrong or apply an undocumented outlier threshold. Volume deltas are calculated only when callers explicitly declare a common volume-unit identifier for every compared provider. Without complete matching declarations, volume discrepancy is null, volume comparability is unverified or incompatible, and the overall result cannot claim consistency solely from matching prices. The comparator does not infer exchange volume semantics, convert units, or treat zero volume as invalid; zero-volume candles remain valid input and are compared only when units are verified. Caller-supplied unit declarations are not independent exchange verification.


### Price-scale and OHLC outlier diagnostics

For each provider pair, the offline comparison now summarizes left-to-right OHLC price ratios across exact shared candle opens (minimum, median, maximum, and max/min spread). It also returns up to five largest individual OHLC discrepancies with timestamp, field, both observed prices, ratio, and symmetric basis-point difference. These are ranked observations, not automatic rejection thresholds: the report does not decide which provider is correct, rescale prices, or infer a unit conversion. Market identity and exact timestamp alignment remain prerequisites, and volume comparability remains independently gated by explicit common-unit declarations.


### Zero, missing, and unusual volume diagnostics

Accepted candle rows must contain an explicit finite, non-negative volume value. A missing volume field is malformed and is never defaulted to zero; negative, NaN, and infinite volume values fail validation. Explicit zero-volume candles remain valid and are counted, with consecutive zero-volume runs reported by their first and last candle opens. Adjacent volume changes (including zero-to-positive and positive-to-zero transitions) and the largest observations relative to the positive-volume median are ranked for inspection. These rankings do not use a universal spike threshold, do not imply manipulation or provider failure, and do not reject otherwise valid candles. A zero-volume interval may reflect venue-specific no-trade semantics; interpretation requires provider context. Volume comparisons across providers remain withheld unless every provider explicitly declares the same volume-unit identifier.

### Cross-provider volume discrepancy diagnostics

When (and only when) every compared provider has an explicit matching volume-unit declaration, pairwise reports include exact-shared-timestamp volume observations, the five largest discrepancies, and a separate count of zero-versus-positive disagreements. A one-sided zero is surfaced as a distinct pattern rather than being hidden by a ratio or division-by-zero calculation; both-zero and both-positive observations are also distinguished. Without verified common-unit declarations, these fields are withheld. The diagnostics do not infer which provider is correct, convert units, or label a discrepancy as manipulation or feed failure.


### Provider-specific volume semantics and provenance

The normalized `volume` field retains the provider's raw candle-volume value; CIN does not convert it. The `/market-candles` response includes a `volume_semantics` descriptor for the selected source. Binance Spot REST distinguishes kline `Volume` from `Quote asset volume`, so CIN records the former as base-asset volume and identifies the market base asset as its unit asset. Kraken Spot REST OHLC and Coinbase Exchange REST product-candle schemas expose a field named `volume`, but the endpoint schemas reviewed for this adapter do not explicitly identify its base/quote asset basis. CIN therefore labels those bases `unknown` rather than importing assumptions from another product, API family, or provider convention. Unknown and unsupported providers also remain unknown.

This descriptor is source-schema evidence, not a guarantee that every provider implementation or market is correct. The offline comparator's existing `volume_unit_by_provider` argument remains a caller-supplied declaration; matching strings do not become independently source-verified merely because they match. Cross-provider volume analysis must not be described as exchange-verified unless a separate source-verified semantics record establishes the same basis and asset for every compared provider. No unit conversion, automatic provider ranking, or trading action is performed.


### Source-verified volume comparability gate

Matching strings supplied through `volume_unit_by_provider` are caller declarations only. They are retained in the report as `caller_declared_volume_units_match`, with status `caller_declared_matching_unit_only`; they do not enable volume deltas, zero/positive mismatch counts, or volume tolerance results. To authorize those diagnostics, callers must provide `volume_semantics_by_provider` descriptors that exactly match CIN's maintained provider evidence registry, and every provider's verified basis and asset must match the explicitly supplied common market identity. A caller cannot upgrade an unknown provider basis by editing a descriptor: unrecognized or modified descriptors fail closed. Current registry evidence marks Binance Spot kline volume as base-asset volume, while Kraken OHLC and Coinbase Exchange candle volume remain unknown. Consequently, the currently supported Binance/Kraken/Coinbase combination does not yet qualify for source-verified cross-provider volume comparison. Price comparisons remain independently available. No unit conversion or provider ranking is performed.
