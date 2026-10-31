# CIN Public Market Candles and Market-Backed Technical Analysis

These read-only endpoints use public exchange market-data endpoints. Provider selection may fall back from Binance to Kraken and then Coinbase for eligible pairs/timeframes. They do not require API credentials and do not access accounts or place orders.

## 1. Retrieve timestamped candles

`GET /market-candles?symbol=BTCUSDT&interval=1h&limit=100`

- `symbol`: public market pair such as `BTCUSDT`
- `interval`: supported Binance kline interval (for example `15m`, `1h`, `4h`, `1d`)
- `limit`: 5–500 candles
- Response includes OHLCV, open/close timestamps in milliseconds and UTC ISO format, source, retrieval time, and limitations.

## 2. Run technical analysis from public candles

`GET /technical-analysis/market?symbol=BTCUSDT&interval=1h&limit=100`

This fetches public candles and passes OHLC values into CIN's existing deterministic analysis engine (market structure, RSI, MACD, ATR, swing reference levels, and illustrative ATR scenarios). The response includes source, symbol, timeframe, retrieval time, and first/last candle times.

## Reliability and safety notes

- Data comes from the selected public exchange provider (Binance, Kraken, or eligible Coinbase fallback) and is not independently audited by CIN.
- The most recent candle may still be forming. Use timestamped snapshots and account for that when comparing signals. Responses classify completed-candle freshness as `fresh`, `stale`, or `no_completed_candle` using a two-interval age threshold; `is_stale` is `true`, `false`, or `null` respectively. A stale snapshot is explicitly labelled and must not be presented as live.
- Binance HTTP 451 may trigger Kraken and then Coinbase public-data fallback; provider rate limits and unavailable fallbacks return a retryable 503 rather than stale data.
- Coinbase fallback is restricted to USD-quoted pairs (for example, `BTCUSD`). A USDT request is not substituted with a USD product; quote assets are not interchangeable.
- Coinbase candle rows are screened for finite positive OHLC values, non-negative finite volume, valid OHLC ranges, and whole-second timestamps within the supported datetime range; invalid rows are excluded.
- The offline `compare_provider_candles` diagnostic compares already-fetched snapshots for the same market: exact timestamp overlap, provider-specific missing timestamps, timeline gaps, OHLC discrepancy in basis points, and volume discrepancy in basis points. It does not fetch data, interpolate timestamps, choose a trusted provider, or independently verify symbol/quote identity.
- Unsupported symbols/intervals and invalid limits are rejected.
- Volume is returned as provider context but is not yet used in indicator calculations.
- No credentials, user accounts, order placement, or trade execution are involved.
- RSI/MACD/ATR and structure labels are descriptive analytical outputs, not guaranteed predictions or financial advice.
