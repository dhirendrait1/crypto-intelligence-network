import { describe, expect, it } from "vitest";
import { validateCoinbaseCandlesPayload } from "./api";

const validPayload = () => ({
  service: "cin",
  mode: "read_only",
  source: "coinbase_exchange_public",
  source_endpoint: "/products/BTC-USD/candles",
  product_id: "BTC-USD",
  quote_currency: "USD",
  granularity: "1h",
  requested_start_utc: "2026-10-30T00:00:00Z",
  requested_end_utc: "2026-10-31T00:00:00Z",
  retrieved_at: "2026-10-31T00:00:00Z",
  count: 1,
  latest_closed_candle_close_time_utc: "2026-10-30T23:00:00Z",
  latest_closed_candle_age_seconds: 3600,
  stale_threshold_seconds: 7200,
  stale_data_warning: null,
  data: [{
    open_time: 1793401200, close_time: 1793404799,
    open: 100, high: 110, low: 95, close: 105, volume: 12,
    open_time_utc: "2026-10-30T23:00:00Z",
    close_time_utc: "2026-10-30T23:59:59Z",
    is_closed: true,
  }],
  limitations: ["Public exchange data only."],
});

describe("Coinbase public candle frontend contract", () => {
  it("accepts a correctly identified read-only USD response", () => {
    expect(validateCoinbaseCandlesPayload(validPayload(), "BTC-USD", "1h").valid).toBe(true);
  });
  it("rejects non-object payloads and responses not marked read-only", () => {
    expect(validateCoinbaseCandlesPayload(null, "BTC-USD", "1h").valid).toBe(false);
    const payload = validPayload();
    payload.mode = "trading";
    expect(validateCoinbaseCandlesPayload(payload, "BTC-USD", "1h").valid).toBe(false);
  });
  it("rejects a mismatched product, quote currency, or interval", () => {
    const payload = validPayload();
    expect(validateCoinbaseCandlesPayload(payload, "ETH-USD", "1h").valid).toBe(false);
    payload.quote_currency = "USDT" as "USD";
    expect(validateCoinbaseCandlesPayload(payload, "BTC-USD", "1h").valid).toBe(false);
    const otherInterval = validPayload();
    otherInterval.granularity = "5m";
    expect(validateCoinbaseCandlesPayload(otherInterval, "BTC-USD", "1h").valid).toBe(false);
  });
  it("rejects count mismatches and non-finite numeric candle fields", () => {
    const countMismatch = validPayload();
    countMismatch.count = 2;
    expect(validateCoinbaseCandlesPayload(countMismatch, "BTC-USD", "1h").valid).toBe(false);
    const nonFinite = validPayload();
    nonFinite.data[0].close = Number.NaN;
    expect(validateCoinbaseCandlesPayload(nonFinite, "BTC-USD", "1h").valid).toBe(false);
  });
  it("rejects invalid OHLC bounds, negative volume, and reversed candle times", () => {
    const badOhlc = validPayload();
    badOhlc.data[0].high = 99;
    expect(validateCoinbaseCandlesPayload(badOhlc, "BTC-USD", "1h").valid).toBe(false);
    const badVolume = validPayload();
    badVolume.data[0].volume = -1;
    expect(validateCoinbaseCandlesPayload(badVolume, "BTC-USD", "1h").valid).toBe(false);
    const badTime = validPayload();
    badTime.data[0].close_time = 1;
    expect(validateCoinbaseCandlesPayload(badTime, "BTC-USD", "1h").valid).toBe(false);
  });
  it("rejects missing provenance and malformed timestamp metadata", () => {
    const noSource = validPayload();
    noSource.source = "";
    expect(validateCoinbaseCandlesPayload(noSource, "BTC-USD", "1h").valid).toBe(false);
    const noTimestamp = validPayload();
    noTimestamp.data[0].open_time_utc = "not-a-date";
    expect(validateCoinbaseCandlesPayload(noTimestamp, "BTC-USD", "1h").valid).toBe(false);
  });
});
