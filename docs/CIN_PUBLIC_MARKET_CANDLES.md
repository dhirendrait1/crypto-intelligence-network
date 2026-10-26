# CIN Public Market Candles and Market-Backed Technical Analysis

These read-only endpoints retrieve public OHLCV candles without API credentials, account access, or order execution.

## 1. Retrieve timestamped candles

`GET /market-candles?symbol=BTCUSDT&interval=1h&limit=100`

- `symbol`: uppercase public market pair, such as `BTCUSDT` or `ETHUSD`
- `interval`: supported candle interval. The primary Binance provider supports the intervals accepted by the endpoint; the Kraken fallback supports only `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, and `1w`.
- `limit`: 5–500 candles
- Response includes OHLCV, open/close timestamps in milliseconds and UTC ISO format, source, retrieval time, and limitations.

## 2. Run technical analysis from public candles

`GET /technical-analysis/market?symbol=BTCUSDT&interval=1h&limit=100`

This fetches public candles and passes OHLC values into CIN's deterministic analysis engine (market structure, RSI, MACD, ATR, swing reference levels, and illustrative ATR scenarios). The response includes the actual provider source and endpoint, symbol, timeframe, retrieval time, and first/last candle times.

## Provider selection and fallback

1. CIN tries Binance's public klines endpoint first.
2. If Binance responds with HTTP 451, CIN attempts Kraken's public OHLC endpoint for supported USD/USDT pairs and intervals.
3. Responses identify the provider actually used. If Kraken cannot supply valid data, CIN returns an explicit error rather than fabricating candles or claiming that Binance data was returned.
4. A Binance rate-limit response (HTTP 418/429) is surfaced as a retryable service error; it does not trigger the HTTP-451 fallback path.

The fallback is best-effort. Pair availability, provider policies, regional access, and rate limits can change. The code's supported-pair mapping is not a guarantee that every pair is listed by Kraken. Verify live provider availability before relying on a specific symbol.

## Reliability and analytical limitations

- Provider data is public and is not independently audited by CIN.
- The most recent candle may still be forming. Treat the latest candle as provisional unless its close time is in the past.
- OHLCV values and technical indicators are descriptive inputs, not guaranteed predictions or financial advice.
- Volume is returned as provider context but is not currently used in indicator calculations.
- Provider failures must not be silently replaced with stale data.
- No credentials, user accounts, wallet access, order placement, or trade execution are involved.

## Verification

Offline tests cover response shape and provenance, invalid input, rate-limit handling, Binance HTTP-451 fallback selection, and explicit fallback failure. These tests do not prove that a live provider currently serves a particular pair or that the deployed Render instance has received the latest commit. Confirm live behavior separately after deployment.
