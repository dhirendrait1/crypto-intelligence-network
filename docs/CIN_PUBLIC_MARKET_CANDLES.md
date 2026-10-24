# CIN Public Market Candles and Market-Backed Technical Analysis

These read-only endpoints use public exchange market data. Binance is the primary provider; the API attempts Kraken public OHLC as a fallback only when Binance responds with HTTP 451. No API credentials or account access are used, and no orders are placed.

## 1. Retrieve timestamped candles

`GET /market-candles?symbol=BTCUSDT&interval=1h&limit=100`

- `symbol`: public market pair such as `BTCUSDT`
- `interval`: supported interval (for example `15m`, `1h`, `4h`, `1d`); Kraken fallback supports only its explicitly mapped intervals
- `limit`: 5–500 candles
- Response includes OHLCV, millisecond and UTC ISO timestamps, provider/source attribution, retrieval time, candle status, freshness metadata, and limitations.
- The latest candle can be forming; inspect `data[].is_closed` / `data[].candle_status` before using a snapshot as completed data.

## 2. Run technical analysis from public candles

`GET /technical-analysis/market?symbol=BTCUSDT&interval=1h&limit=100`

This fetches public OHLCV candles and passes **completed candles only** to CIN's deterministic analysis engine (market structure, RSI, MACD, ATR, swing reference levels, volume context, and illustrative ATR scenarios). The response reports requested, used, and excluded-forming candle counts, source provenance, freshness metadata, and first/last analyzed candle times. Fewer than five completed candles returns HTTP 422.

## Request validation and provider errors

- Malformed symbols, unsupported intervals, and limits outside 5–500 are rejected with HTTP 400 by the endpoint's explicit validation.
- Binance HTTP 418/429 rate limits return HTTP 503; other Binance HTTP errors return a controlled gateway error.
- Kraken fallback is attempted only after Binance HTTP 451. If fallback fails or the pair/timeframe is unsupported, the API returns HTTP 503 rather than claiming stale data is live.
- Network/provider unavailability returns a controlled 503; malformed provider responses return a controlled 502.
- Freshness compares the latest completed candle age with twice the requested interval; monthly intervals use a 31-day approximation.
- Public provider data is not independently audited by CIN. Provider pair identifiers and quote currency can differ from the requested symbol and are reported separately.
- Volume is included in analysis input and may contribute volume metrics when valid; it is not a guarantee of market liquidity or executable depth.
- RSI/MACD/ATR and structure labels are descriptive research outputs, not guaranteed predictions, investment advice, or trade instructions.
- No credentials, user accounts, order placement, wallet control, or trade execution are involved.

## Duplicate timestamp consistency

Valid candles are sorted chronologically. Identical duplicate rows with the same open timestamp are collapsed into one row. If the same provider response contains different OHLCV or close-time values for the same open timestamp, the provider response is rejected as conflicting evidence rather than silently selecting whichever row appeared last. This is an offline-tested data-integrity guard; it does not compare Binance and Kraken prices simultaneously or establish cross-exchange equivalence.
