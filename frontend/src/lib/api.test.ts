import { afterEach, describe, expect, it, vi } from "vitest";
import { cinApi, validateCoinbaseCandlesPayload } from "./api";

const candle = (openTime: number) => ({
  open_time: openTime, close_time: openTime + 59, open: 100, high: 105, low: 95, close: 102, volume: 10,
  open_time_utc: new Date(openTime * 1000).toISOString(),
  close_time_utc: new Date((openTime + 59) * 1000).toISOString(),
  is_closed: true,
});

const validPayload = (data: ReturnType<typeof candle>[]) => ({
  service: "cin", mode: "read_only", source: "coinbase", source_endpoint: "/products/BTC-USD/candles",
  product_id: "BTC-USD", quote_currency: "USD", granularity: "1m",
  requested_start_utc: new Date(0).toISOString(), requested_end_utc: new Date(120000).toISOString(),
  retrieved_at: new Date(180000).toISOString(), count: data.length,
  latest_closed_candle_close_time_utc: null, latest_closed_candle_age_seconds: null,
  stale_threshold_seconds: 120, stale_data_warning: null, data, limitations: [],
});

describe("CIN API client configuration", () => {
  afterEach(() => vi.unstubAllEnvs());
  it("does not invent a production API origin when no environment URL is supplied", () => {
    expect(cinApi.configured).toBe(false);
  });
});

describe("Coinbase candle response contract", () => {
  it("accepts strictly increasing candle open timestamps", () => {
    expect(validateCoinbaseCandlesPayload(validPayload([candle(60), candle(120)]), "BTC-USD", "1m").valid).toBe(true);
  });

  it("rejects a candle timestamp that is not aligned to its requested interval", () => {
    const payload = { ...validPayload([candle(60)]), granularity: "5m" };
    const result = validateCoinbaseCandlesPayload(payload, "BTC-USD", "5m");
    expect(result.valid).toBe(false);
    expect(result.message).toContain("not aligned to the requested interval boundary");
  });

  it("accepts a candle timestamp aligned to a five-minute UTC boundary", () => {
    const payload = { ...validPayload([candle(300)]), requested_start_utc: new Date(300_000).toISOString(), requested_end_utc: new Date(600_000).toISOString(), granularity: "5m" };
    expect(validateCoinbaseCandlesPayload(payload, "BTC-USD", "5m").valid).toBe(true);
  });

  it("rejects unsupported candle intervals", () => {
    const payload = { ...validPayload([candle(60)]), granularity: "2m" };
    const result = validateCoinbaseCandlesPayload(payload, "BTC-USD", "2m");
    expect(result.valid).toBe(false);
    expect(result.message).toContain("interval is not supported");
  });

  it("rejects duplicate candle open timestamps instead of silently accepting ambiguous rows", () => {
    const result = validateCoinbaseCandlesPayload(validPayload([candle(60), candle(60)]), "BTC-USD", "1m");
    expect(result.valid).toBe(false);
    expect(result.message).toContain("strictly increasing");
    expect(result.message).toContain("no duplicates");
  });

  it("rejects UTC timestamps that disagree with numeric epoch fields", () => {
    const mismatched = { ...candle(60), open_time_utc: new Date(61_000).toISOString() };
    const result = validateCoinbaseCandlesPayload(validPayload([mismatched]), "BTC-USD", "1m");
    expect(result.valid).toBe(false);
    expect(result.message).toContain("UTC timestamps do not match");
  });

  it("rejects a mismatched close-time UTC value", () => {
    const mismatched = { ...candle(60), close_time_utc: new Date(121_000).toISOString() };
    const result = validateCoinbaseCandlesPayload(validPayload([mismatched]), "BTC-USD", "1m");
    expect(result.valid).toBe(false);
    expect(result.message).toContain("UTC timestamps do not match");
  });

  it("rejects candles outside the declared request window", () => {
    const result = validateCoinbaseCandlesPayload(validPayload([candle(180)]), "BTC-USD", "1m");
    expect(result.valid).toBe(false);
    expect(result.message).toContain("outside the requested UTC window");
  });

  it("rejects an inverted requested UTC window", () => {
    const payload = { ...validPayload([candle(60)]), requested_start_utc: new Date(120_000).toISOString(), requested_end_utc: new Date(0).toISOString() };
    const result = validateCoinbaseCandlesPayload(payload, "BTC-USD", "1m");
    expect(result.valid).toBe(false);
    expect(result.message).toContain("starts after it ends");
  });

  it("rejects response window metadata that differs from the actual client request", () => {
    const result = validateCoinbaseCandlesPayload(validPayload([candle(60)]), "BTC-USD", "1m", 30, 120);
    expect(result.valid).toBe(false);
    expect(result.message).toContain("does not match the client request parameters");
  });

  it("accepts response window metadata that exactly matches the client request", () => {
    const result = validateCoinbaseCandlesPayload(validPayload([candle(60)]), "BTC-USD", "1m", 0, 120);
    expect(result.valid).toBe(true);
  });
});
