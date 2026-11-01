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


### Independent endpoint-schema evidence audit

The source links exposed in `volume_semantics.evidence_url` identify the exact provider documentation reviewed for each adapter:

- Binance Spot REST klines: the kline response schema distinguishes `Volume` ([5]) from `Quote asset volume` ([7]). CIN records [5] as base-asset volume; the descriptor remains scoped to this Spot endpoint and schema.
- Kraken Spot REST OHLC: the official endpoint example shows positional OHLC rows and CIN maps `ohlc_row[6]` to its normalized `volume` field. The endpoint page does not define that position as base-asset or quote-asset quantity. The separate AssetPairs metadata identifies market assets, but does not, by itself, assign a denomination to the OHLC volume position. CIN therefore retains `unit_basis: unknown`.
- Coinbase Exchange REST product candles: the official endpoint describes the final array item as `volume` / "volume of trading activity" but does not state whether it is denominated in the base or quote asset. CIN therefore retains `unit_basis: unknown`. Coinbase Data Marketplace OHLCV documentation is a different product dataset and is not evidence for the Exchange REST candle endpoint; its base-currency definition is not imported into this adapter.

These findings are deliberately endpoint-specific. A field name, positional example, SDK type named `volume`, or analogous dataset from another API family is not sufficient to upgrade an unknown basis. A future registry change requires direct documentation for the exact endpoint and an explicit denomination statement. The evidence URL is provenance for the review, not a claim that the source page guarantees data correctness.


### Canonical market-identity token handling

The offline cross-provider comparator trims surrounding whitespace and uppercases explicitly supplied base-asset and quote-asset identifiers before comparing them. This is presentation normalization only; CIN does not infer that exchange-specific aliases are equivalent. For example, `BTC` and `XBT` remain different identities unless the caller supplies the same reviewed canonical asset identifier for both provider snapshots. Quote assets are never substituted: `USD` and `USDT` remain distinct. Empty or malformed identifiers fail closed. This normalization does not parse trading symbols, resolve exchange products, or independently verify that caller-supplied market identity matches the provider response.


### Explicit fallback symbol parsing boundary

Kraken and Coinbase fallback adapters now share one parser for concatenated symbols and recognize only the explicitly supported quote suffixes `USDT` and `USD`, checking the longer suffix first. This prevents an unsupported quote such as `USDC` from being split into a plausible but incorrect base/quote pair. Coinbase still refuses to substitute a USD product for a USDT request. The parser is syntactic validation only: it does not prove that a base asset or product is listed by an exchange. Kraken performs its separate AssetPairs catalogue lookup and verifies the returned `altname`, `wsname`, and OHLC result key. Coinbase product-catalogue verification remains a separate follow-up; the current candle adapter constructs the requested USD product identifier but does not independently retrieve its product metadata.


### Coinbase product-catalogue identity verification

Before requesting fallback candles, CIN retrieves the public Coinbase Exchange products catalogue and requires exactly one record with the constructed product `id`. Its `base_currency` and `quote_currency` must exactly match the requested base/quote assets. A missing product is treated as an unavailable market; a malformed catalogue, duplicate product identifier, or base/quote mismatch is rejected as a provider data-integrity failure. The candle endpoint is not called after any of those failures. This is a read-only catalogue cross-check, not a guarantee of liquidity, tradability, or data correctness; the returned candle rows remain subject to the existing independent integrity checks.


### Kraken AssetPairs field-level market identity integrity

Before the OHLC request, CIN now requires the AssetPairs record to contain non-empty `base` and `quote` asset IDs in addition to the existing `altname` and `wsname` checks. It validates the canonical result key against the concatenated raw asset IDs and compares the requested base/quote only after applying a small explicit Kraken REST alias map (`XXBT` to `XBT`, `ZUSD` to `USD`). Other asset IDs are not inferred or rewritten. Missing fields, conflicting asset IDs, a result-key mismatch, or more than one returned market record fail closed before the OHLC request. This is market-identity validation only; it does not imply market liquidity, trading eligibility, or provider-data correctness.

The field meanings and Kraken-specific symbol variants are documented in Kraken's [API symbols and tickers reference](https://support.kraken.com/articles/360000920306-api-symbols-and-tickers), which shows AssetPairs records carrying `base`, `quote`, `altname`, and `wsname` and explains the distinct REST/WebSocket symbol forms.


### Kraken AssetPairs asset-class validation

CIN now also requires `aclass_base` and `aclass_quote` to equal `currency` before accepting a Kraken AssetPairs record for this spot-currency candle adapter. Missing fields and other asset classes (including tokenized-asset classes) are rejected before the OHLC request. This keeps the adapter's supported scope explicit rather than treating every Kraken AssetPairs instrument as an interchangeable spot-currency market. Kraken documents these asset-class fields separately from the base and quote asset identifiers; the current spot-currency examples report `currency` for both sides.

Reference: [Kraken API symbols and tickers](https://support.kraken.com/articles/360000920306-api-symbols-and-tickers) and [Kraken Spot AssetPairs response example](https://python-kraken-sdk.readthedocs.io/en/stable/04_spot/rest.html).


### Kraken AssetPairs market-status integrity

CIN requires the Kraken AssetPairs `status` field to be present, non-empty, and exactly `online` before requesting OHLC candles. This candle adapter uses an intentionally conservative availability policy: known restricted or unavailable states (`cancel_only`, `post_only`, `limit_only`, `reduce_only`, `maintenance`, `delisted`, `suspended`, and `hidden`) are rejected rather than treated as fully available. A missing, empty, malformed, or non-string status is rejected as missing/invalid metadata; an unrecognized status is rejected as unknown. Status comparisons are exact and case-sensitive so unexpected provider values cannot silently pass. Each rejected market is isolated to its own request and is rejected before the OHLC endpoint is called. This is a read-only data-eligibility gate, not an order-routing or trading-control feature.

Kraken describes the trading modes and their operational restrictions in its [possible trading modes reference](https://support.kraken.com/ca/articles/360055614211-what-are-the-possible-trading-modes-) and [Spot FIX instrument status reference](https://docs-legacy.kraken.com/api/docs/fix-api/sl-fix/). The AssetPairs response example also includes a per-pair `status` field in the [Kraken Spot SDK documentation](https://python-kraken-sdk.readthedocs.io/en/stable/04_spot/rest.html).


### Provider freshness threshold and stale-snapshot handling

CIN classifies freshness using the latest completed candle, not the latest row when that row may still be forming. The current threshold is two requested-interval durations: an age exactly equal to the threshold remains `fresh`; an age greater than the threshold is `stale`. A snapshot with no completed candle is reported as `no_completed_candle`, with no stale/fresh boolean inferred from a forming row. Future candle opens remain invalid.

Staleness is an explicit quality warning, not a transport failure and not proof that an exchange feed is unavailable. The provider loader does not silently replace a valid-but-stale primary snapshot with another venue's data. Provider fallback remains limited to the existing transport-failure and documented HTTP 451 paths; rate limits and malformed successful payloads retain their separate classifications. This avoids disguising stale data as current data or changing the market venue without an explicit source label. Consumers must inspect `freshness_status`, `is_stale`, `latest_closed_candle_age_seconds`, and `stale_threshold_seconds` before treating a snapshot as current. CIN does not synthesize candles or upgrade a stale snapshot's status.


### Provider failure classification and fallback-chain provenance

CIN keeps provider failure classes distinct so a fallback does not hide a rate limit, access denial, malformed successful payload, or ambiguous candle response. Binance HTTP 418/429 remains a rate-limit stop; HTTP 451 and transport failures may proceed to Kraken. Kraken HTTP 418/429 is also a rate-limit stop, and HTTP 401/403 is an access-denial stop; neither is retried through Coinbase. Kraken HTTP failures other than rate-limit/access-denial responses, and Kraken transport/data failures, may proceed to Coinbase under the existing fallback policy. Malformed Kraken candle rows remain a fail-closed integrity error. Coinbase rate limits and unsuccessful/malformed responses terminate the chain with an explicit unavailable/error result.

When Coinbase is selected after a Kraken failure, the source label records both the original Binance trigger and the intermediate Kraken failure class/status. The final provider identity and endpoint must agree across every candle row and the selected source. CIN does not combine candles from multiple venues, retry rate-limited providers, or silently switch providers after a malformed successful response. These rules apply only to public read-only market data.


### Cross-provider discrepancy severity

The offline provider comparison reports per-pair price and, only when source-verified common volume units exist, volume discrepancy severity. Severity is relative to the caller's configured basis-point tolerance: `within_tolerance` is at or below tolerance; `minor` is above tolerance through 2×; `elevated` is above 2× through 5×; and `critical` is above 5× or an unbounded discrepancy. A metric with no comparable observations is `not_assessable`. The report also summarizes the number of provider pairs with elevated or critical observations.

Severity is advisory data-quality metadata, not a provider ranking, automatic source switch, trading signal, or proof that one venue is correct. Exact candle-open alignment, common canonical base/quote identity, and evidence-backed volume units remain prerequisites for the corresponding comparisons. Caller-declared matching volume units alone do not establish source-verified comparability. The comparison remains offline and read-only; it does not fetch, repair, merge, or synthesize provider candles.


### Historical candle continuity and recovery boundaries

CIN's offline historical continuity assessment validates the supplied candles against the requested interval, orders them by open time, and reports internal missing intervals between observed candles. Duplicate, overlapping, malformed, or timeframe-misaligned rows are rejected. It does not infer missing candles from leading or trailing edges because a requested historical start/end window is required to establish those boundaries. Consequently, window completeness remains explicitly unknown when those bounds are not supplied.

Detected gaps are integrity findings, not instructions to synthesize or interpolate OHLCV values. This assessment does not backfill, repair, merge provider snapshots, or silently replace a valid but incomplete history with another provider. Any future recovery workflow must request a bounded missing time range from an eligible provider, retain provider provenance, revalidate market identity and interval alignment, and preserve the original gap/recovery audit trail. No automatic recovery or additional provider polling is enabled by this helper.


### Bounded historical pagination and recovery-window limits

The Coinbase Exchange fallback accepts only the same maximum 500-candle request window exposed by the public CIN candle route. With a provider page cap of 300 candles, the adapter is explicitly limited to at most two sequential requests per snapshot. Each page uses a granularity-aligned, adjacent time window; the cursor must advance, and any attempt to exceed the two-page budget fails closed. A response may include the single immediately preceding boundary candle, which is retained only when it falls within the requested overall window; identical repeated timestamps are deduplicated, while conflicting rows are rejected. This is bounded retrieval of one provider snapshot, not a retry loop or cross-provider recovery process. Binance remains a single bounded request; Kraken remains a single OHLC response with its `last` field validated as a continuation cursor but not used to paginate because the endpoint response is capped and the public CIN request is below that cap. No additional provider polling, automatic backfill, or data synthesis is enabled.


### Provider response-body completeness and size limits

Every public provider HTTP response is read with a fixed 2 MiB ceiling (one extra byte is requested to detect overflow) and a 15-second network timeout. A successful HTTP response that exceeds the body ceiling, ends with an incomplete HTTP body, contains invalid UTF-8, or does not contain valid JSON is classified as malformed provider data. It must not be reclassified as a transport outage or trigger the next provider in the fallback chain. Genuine connection failures and timeouts remain transport failures under the existing policy. Provider-specific wrappers preserve the malformed-success classification. Regression tests exercise incomplete bodies, oversized bodies, invalid encoding, and truncated JSON using mocked responses; they do not contact exchanges. The response cap is a byte bound, not a claim that a syntactically valid JSON document is semantically complete: provider-specific envelope, pagination, row-count, timestamp, and candle validations remain separately required.


### Provider JSON schema and field-type integrity

The adapter now rejects booleans, nulls, objects, and arrays in scalar candle fields before numeric coercion. This prevents Python's permissive conversions (for example, booleans converting to 0/1) from turning structurally invalid JSON into plausible market values. The check is applied to the consumed Binance, Kraken, and Coinbase candle positions; existing provider-specific timestamp, OHLCV, alignment, and row-count validation remains in force. Kraken error-envelope entries must be strings, while the envelope itself must remain a list. These are strict type checks, not assumptions that every optional field in a provider response is mandatory. Provider schema changes should be reviewed explicitly rather than silently coerced. Mocked regression tests cover boolean/nested scalar rejection and malformed Kraken error entries; no live provider calls are made by these tests.


### Provider timestamp units and UTC normalization

CIN now parses provider timestamps against an explicit endpoint-specific unit contract before normalization. Binance Spot kline open/close timestamps must be integer Unix milliseconds; Kraken OHLC and Coinbase Exchange candle opens must be integer Unix seconds. Values that resemble the other unit, booleans, negative values, fractions, non-finite numbers, and values outside the supported Python UTC datetime range are rejected rather than guessed or silently rescaled. Numeric strings remain accepted because these endpoints serialize timestamp fields as numeric JSON values or numeric strings in their documented response forms. Normalized internal timestamps are integer Unix milliseconds and are interpreted in UTC; no local timezone offset or daylight-saving adjustment is applied. These checks complement, and do not replace, the existing provider-specific timeframe-boundary and candle-duration validation. Tests are offline and do not contact exchanges.


### Provider response ordering and deterministic normalization

The shared candle normalizer returns a new list in ascending UTC open-time order and does not mutate the provider-owned input sequence. The canonical result is independent of the input permutation when every open timestamp is unique. Sorting is a normalization step, not permission to discard ambiguous source records: any repeated open timestamp is rejected. Identical duplicate rows are classified separately from conflicting rows, and both fail closed; conflicting OHLCV values are never resolved by first-row/last-row wins, averaging, or provider preference. Overlapping candle time ranges remain invalid after ordering.

Adapter behavior is intentionally preserved where endpoint contracts differ: Kraken validates strictly increasing timestamps in its original response sequence and rejects duplicates or descending rows at the adapter boundary. Coinbase's bounded page collector sorts its timestamp-keyed snapshot and permits an identical row repeated at a pagination boundary, but rejects conflicting rows for that timestamp. Binance rows are validated individually and then pass through the shared canonical normalizer, which orders unique timestamps and rejects duplicate or overlapping intervals. These distinctions are covered by offline regression tests; no live provider calls, data repair, interpolation, or candle synthesis are performed.


### Canonical provider snapshot contract and bounded completeness

After provider-specific parsing and shared candle normalization, every snapshot row must contain the canonical OHLCV fields (`open_time`, `open`, `high`, `low`, `close`, `volume`, `close_time`) and one coherent provenance tuple (`_provider`, `_source`, `_source_endpoint`). The snapshot validator rejects missing canonical fields, invalid open-time types, non-chronological or repeated opens, mixed provider attribution, and a row count greater than the original requested limit. This is a common post-adapter contract; Binance, Kraken, and Coinbase retain their endpoint-specific parsing and eligibility rules.

A snapshot shorter than the requested limit is accepted as partial evidence, not silently padded or automatically replaced with another venue. The API separately reports returned-row coverage and requested-window edge coverage. These measures answer different questions: returned count versus requested count, and presence of expected leading/trailing interval opens. Internal gaps remain visible through timeline integrity. Kraken and Coinbase may omit intervals with no trades, so an absent row is not automatically classified as provider feed loss. The cross-provider comparator reports observed union coverage and exact timestamp overlap; it cannot infer completeness against a caller's intended request window unless that window is supplied separately. A comparison over matching partial snapshots is therefore not proof of full-window completeness.

All adapter contract tests use mocked provider payloads. No live exchange polling, row padding, cross-provider candle stitching, interpolation, synthetic data, trade execution, or automatic source switching is performed.

### Freshness propagation in data-quality metadata

Freshness is calculated once per API response from the latest completed candle and the response's UTC clock sample. The nested `data_quality` object now carries the same explicit freshness contract as the top-level response: status, nullable stale boolean, latest completed-candle close time and age, threshold, and warning. A forming-only snapshot is explicitly a quality warning with `no_completed_candle_available`; it is not represented as fresh or stale. This prevents consumers that inspect only the nested quality object from losing the stale-data warning. A stale snapshot remains attributed to its selected provider and is not replaced by a different venue. Deterministic mocked-clock regression tests cover both stale and no-completed-candle propagation.

### Retrieval-time and response-clock consistency

Each market-candles or technical-analysis response samples the UTC clock once after its provider snapshot has been loaded. The same instant supplies the `retrieved_at` ISO-8601 UTC value, the millisecond reference used for completed-candle freshness, and the market-candles `is_closed` flags. This avoids intra-response disagreements caused by independently reading the system clock for each field. Retrieval time is response-generation time after loading, not the provider candle close time and not a provider-supplied exchange timestamp. Provider-specific request-window clocks remain separate implementation details and are not presented as response retrieval time. Offline frozen-clock tests verify the shared reference instant for both response types.



### Machine-readable provider fallback provenance

Both the market-candles response and the technical-analysis input now expose a
`provider_provenance` object. It identifies the primary provider, the provider
that actually supplied the returned snapshot, whether fallback occurred, the
primary-provider trigger (HTTP 451 or transport failure), and any recorded
intermediate Kraken failure. The existing human-readable `source` and exact
`source_endpoint` remain authoritative and must agree with the selected
provider. The metadata is emitted only after the snapshot's rows are checked
for one coherent provider/source/endpoint tuple; mixed attribution fails
closed. A direct Binance response is explicitly marked as no-fallback.
Malformed successful responses, rate limits, access denials, and ambiguous
provider data retain their existing stop/fail-closed behavior and are not
reclassified as fallback-eligible outages. This is source attribution for
read-only research data, not provider quality certification.


### Explicit fallback eligibility matrix

Fallback eligibility is an allow-list, not a generic retry-on-error rule. Binance HTTP 451 and classified transport failures may advance to Kraken. Binance HTTP 418/429 (rate limiting), other HTTP statuses including access denial and server errors, and malformed successful responses stop the chain. If Kraken is reached, HTTP 418/429 stops with a rate-limit response; HTTP 401/403 stops with an access-denial response; other HTTP errors and classified transport/data failures may advance to Coinbase. A malformed successful Kraken response always stops. Coinbase is terminal: its rate limits, HTTP errors, transport failures, unsupported products/timeframes, and malformed responses do not initiate another provider request.

This policy deliberately does not infer that every 5xx, 4xx, parse, or integrity error is transient. Only the explicitly classified branches above are fallback-eligible. Regression tests exercise the Binance and Kraken HTTP-status decision matrices and verify that malformed successful responses do not fan out to the next venue. Tests use mocked responses and make no live exchange requests. Fallback eligibility is solely a read-only data-retrieval policy; it does not retry orders, place trades, or select a venue for execution.


### Fallback response request-integrity contract

Every selected provider response is normalized against the original requested timeframe before it can be returned. Each candle must have a provider-valid UTC open boundary and an exact close timestamp for that timeframe; duplicate, overlapping, malformed, or misaligned rows fail closed. The final snapshot must remain chronologically unique, retain one coherent selected-provider/source/endpoint attribution, and contain no more rows than the original request limit. A shorter provider response remains partial evidence; CIN does not pad it or splice rows from another venue.

Market identity is enforced at the provider adapter boundary rather than inferred from OHLCV values. Binance receives the requested symbol directly. Kraken resolves the requested base/quote against exactly one AssetPairs record, verifies the record's aliases, asset IDs, asset classes, status, and OHLC result key. Coinbase constructs the requested product ID and verifies that the public product catalogue reports the exact requested base and quote currencies before requesting candles. Fallback symbol parsing accepts only the explicitly supported USD and USDT quote forms; unsupported or ambiguous symbols are rejected rather than guessed. These checks preserve the original requested market while allowing only documented exchange-specific aliases such as BTC/XBT.

Offline regression tests cover unsupported fallback symbols, cross-timeframe candle rejection, incorrect close boundaries, response row-count overflow, and mixed provider attribution. Existing adapter tests separately exercise Kraken and Coinbase catalogue identity checks. Tests use mocked payloads and do not contact live exchanges. This contract validates read-only response integrity; it does not assess liquidity, tradability, or execute orders.


### Requested historical-window boundary enforcement

Before a provider snapshot is returned, CIN now validates every candle open against the exact rolling window implied by the original request limit, timeframe, selected provider, and retrieval-time UTC clock. Opens older than the requested window, beyond the current interval, or otherwise outside the provider-aligned expected opens are rejected as an invalid provider sequence. This check runs after provider normalization and before provenance is attached or response data is emitted.

The current interval's candle is allowed to be forming: its open is within the requested window even when its close time is still in the future. The API continues to label that candle as not closed. A future interval open is never accepted. Provider-specific boundaries are retained, including Binance's Monday UTC weekly anchor and Kraken's Thursday UTC weekly anchor; unsupported provider/timeframe combinations fail closed. The check does not require a full row count because exchanges may omit intervals with no trades. Missing rows remain visible as partial coverage and are never synthesized.

Offline regression tests cover the current forming interval, the preceding requested interval, future opens, older-than-requested opens, unaligned opens, and provider-specific weekly anchors. These tests use deterministic timestamps and make no network requests.


### Kraken OHLC pagination cursor integrity

Kraken's OHLC `last` pagination cursor is treated as a provider timestamp, not as an arbitrary numeric marker. CIN validates it with the same strict Unix-seconds parser used for provider timestamps: booleans, fractional values, negative values, non-finite values, and timestamps outside the supported range are rejected. The cursor must also be at or after the latest returned candle open. An invalid cursor makes the successful provider response malformed; it does not trigger silent truncation or a fallback to another venue.

Regression coverage includes missing, null, boolean, fractional, negative, out-of-range, and stale-before-latest cursor values. Tests are offline and use mocked AssetPairs/OHLC payloads.


### Coinbase multi-page boundary consistency

Coinbase candle pages are requested as adjacent granularity-aligned windows. The collector permits the immediately preceding boundary candle when it is returned by a page, but a timestamp repeated at a page boundary is deduplicated only when the complete raw candle row is identical. A conflicting duplicate across pages invalidates the successful provider response; CIN does not choose one page's values or merge fields. The page budget remains fixed at two requests for the public route's maximum 500-candle window, and missing intervals remain partial evidence rather than being filled. Offline tests verify contiguous page boundaries, identical cross-page deduplication, and rejection of conflicting cross-page rows without contacting Coinbase.


### Coinbase product availability and status integrity

Before requesting Coinbase candles, CIN requires exactly one catalogue record with the requested product ID and exact base/quote identity, an explicit recognized `status` of `online`, and an explicit boolean `trading_disabled` value of `false`. Recognized non-online states (`offline` and `delisted`) are unavailable and are not queried for candles. Missing, null, malformed, or unrecognized status values and a missing/non-boolean `trading_disabled` flag are treated as malformed catalogue metadata and fail closed. A disabled product is unavailable. Other product flags that restrict order types are not interpreted as market-data availability; CIN does not place or route orders. Offline regression tests cover online/enabled acceptance through the existing adapter test, non-online states, disabled trading, and missing/unknown/malformed metadata.


### Coinbase candle response ordering and chronology integrity

Coinbase Exchange candle pages are expected newest-first (strictly descending by the raw candle-open timestamp). CIN validates the original row order before converting a valid page to its internal oldest-first sequence. Duplicate timestamps within a page, ascending rows, and any non-monotonic or malformed timestamp sequence invalidate the successful provider response. CIN does not sort, deduplicate, select a winner, or otherwise repair malformed provider rows.

Pages are requested in increasing time windows. After each page passes its native-order check and is explicitly reversed, the combined pagination sequence must remain strictly oldest-first. An identical row repeated at an allowed page boundary is retained once; a conflicting duplicate is rejected. Any other cross-page chronology regression is rejected. This preserves the distinction between a documented provider-order conversion and silent normalization of invalid input.

Offline regression tests cover valid newest-first input, preservation of the original payload, duplicate timestamps, ascending rows, non-monotonic sequences, and malformed rows/timestamps. The adapter additionally enforces page-to-page chronological integrity during pagination. Tests use mocked responses and do not contact Coinbase. This is a read-only data-integrity check; no order or trade functionality is involved.


### Coinbase pagination boundary integrity and sparse intervals

Coinbase pages are requested in adjacent granularity-aligned windows. CIN permits an identical repeated candle only when its open timestamp is exactly the current page's start boundary and the complete raw row matches the previously received row. An identical duplicate elsewhere across pages is malformed; a conflicting duplicate is always rejected. This prevents timestamp-keyed collection from silently masking repeated provider records outside the documented boundary overlap.

CIN preserves gaps in provider candle timestamps. It does not infer that a missing interval is a malformed response, create synthetic zero-volume candles, interpolate OHLCV values, or silently fill gaps. The returned sequence remains strictly increasing, but need not be interval-contiguous because the provider may omit intervals without candle data. Regression tests verify rejection of non-boundary cross-page duplicates and preservation of sparse intervals without synthetic rows.


### Coinbase requested-window coverage and partial history

The candle response reports returned row count and count shortfall against the requested limit separately from historical-window edge integrity. A short response is labelled partial; zero returned rows are a provider failure and are not emitted as a successful empty candle snapshot. The first and last returned open timestamps remain explicit so consumers can inspect observed coverage.

For Coinbase, requested-window integrity counts missing leading and trailing expected opens. This is an edge-coverage diagnostic, not a claim that every interval inside the window must contain a candle. Coinbase may omit intervals with no trades; internal gaps remain represented by timeline-integrity metadata and are never filled. A response with both requested edges present can therefore have complete edge coverage while still containing internal gaps. Conversely, a missing first or last requested candle is reported as partial edge coverage, with the warning explicitly noting that provider no-trade semantics may explain the absence.

Regression tests cover missing first/last requested opens, interior gaps despite complete edges, zero-row responses, and count shortfall metadata. Tests use deterministic timestamps and mocked provider responses; no live Coinbase request is required.
