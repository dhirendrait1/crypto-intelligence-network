# CIN Public Market Candles and Market-Backed Technical Analysis

These read-only endpoints use the Binance public market-data REST endpoint. They do not require API credentials and do not access accounts or place orders.

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

- Data is from the public Binance market-data API and is not independently audited by CIN.
- The most recent candle may still be forming. Use timestamped snapshots and account for that when comparing signals.
- Provider rate limits return a retryable 503; provider failures do not silently fall back to stale data.
- Unsupported symbols/intervals and invalid limits are rejected.
- Volume is returned as provider context but is not yet used in indicator calculations.
- No credentials, user accounts, order placement, or trade execution are involved.
- RSI/MACD/ATR and structure labels are descriptive analytical outputs, not guaranteed predictions or financial advice.

## Provider interval compatibility

- Binance candle rows are checked against the selected interval's open/close boundary rules, including Monday 00:00 UTC weekly opens and calendar-month monthly opens.
- Kraken fallback supports only the intervals listed by `KRAKEN_INTERVALS`. Its Unix-second open timestamps are normalized to milliseconds; close times are derived from the selected minute interval, then checked by the same boundary validator.
- Offline compatibility regressions cover Kraken 1h, 4h, 1d, and 1w candles, including a missing interval between otherwise valid candles. Missing candles are permitted; malformed boundaries and future opens are not.
- The 3d interval intentionally has no assumed epoch anchor. Kraken does not advertise a 3d interval in this adapter. Coinbase has its own supported-granularity mapping and is not represented as an equivalent USDT quote market.
- These are deterministic offline contract tests. They do not establish live Kraken alignment for every market, provider uptime, source authenticity, or deployed behavior; those remain part of authorized live smoke testing.
