# CIN Technical Analysis API

## Endpoint
`POST /technical-analysis`

This read-only endpoint analyzes caller-supplied chronological OHLC bars. It makes no external network calls.

Example request:
```json
{
  "symbol": "ETH",
  "timeframe": "4h",
  "candles": [
    {"open": 100, "high": 103, "low": 99, "close": 102},
    {"open": 102, "high": 105, "low": 101, "close": 104},
    {"open": 104, "high": 106, "low": 102, "close": 103},
    {"open": 103, "high": 107, "low": 102, "close": 106},
    {"open": 106, "high": 108, "low": 105, "close": 107}
  ]
}
```

The example is intentionally short; RSI(14) needs at least 15 bars, ATR(14) needs at least 15 bars, and the MACD signal line first becomes available at 34 bars (35+ is recommended for additional context). Use up to 500 bars, oldest first.

## Output
- Confirmed swing high/low pattern labels (HH/HL/LH/LL where enough swings exist).
- Simple structure event (BOS/CHOCH) based on last close versus latest confirmed swing.
- RSI(14), MACD(12,26,9), ATR(14) when enough data exists. Flat RSI input resolves to 50; monotonic gains/losses resolve to 100/0. A zero prior-volume baseline leaves relative volume unavailable rather than dividing by zero.
- Swing highs/lows as liquidity reference levels; these are not actual order-book liquidity.
- T1/T2/T3 as illustrative 1x/2x/3x ATR scenarios only when bias is directional.

## Limitations
Input data is caller-supplied and not independently verified. Swing pivots use a two-candle confirmation window and may lag. Targets are volatility scenarios, not forecasts, entry/exit instructions, or guarantees. No trade or order execution is supported.
