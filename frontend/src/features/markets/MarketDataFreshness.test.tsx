import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarketDataFreshness } from "./MarketDataFreshness";
import type { ApiResult, CoinbaseCandlesResponse } from "../../lib/api";

const payload: CoinbaseCandlesResponse = {
  service: "cin", mode: "read_only", source: "Coinbase Exchange", source_endpoint: "/products/BTC-USD/candles",
  product_id: "BTC-USD", quote_currency: "USD", granularity: "1h",
  requested_start_utc: "2026-10-30T00:00:00Z", requested_end_utc: "2026-10-31T00:00:00Z",
  retrieved_at: "2026-10-31T00:00:00Z", count: 1, latest_closed_candle_close_time_utc: "2026-10-30T23:00:00Z",
  latest_closed_candle_age_seconds: 3600, stale_threshold_seconds: 7200, stale_data_warning: null,
  data: [{ open_time: 1793401200, close_time: 1793404799, open: 100, high: 101, low: 99, close: 100, volume: 5, open_time_utc: "2026-10-30T23:00:00Z", close_time_utc: "2026-10-30T23:59:59Z", is_closed: true }],
  limitations: [],
};
const result = (state: ApiResult<CoinbaseCandlesResponse>["state"], data: CoinbaseCandlesResponse | null = payload): ApiResult<CoinbaseCandlesResponse> => ({ state, data, retrievedAt: "2026-10-31T00:00:00Z", source: "Coinbase Exchange", message: "Test state" });

describe("Market data freshness panel", () => {
  it("shows backend age, threshold, count, and source metadata", () => {
    render(<MarketDataFreshness result={result("fresh")} />);
    expect(screen.getByRole("status").textContent).toBe("FRESH");
    expect(screen.getByText("1.0 hr")).toBeTruthy();
    expect(screen.getByText("2.0 hr")).toBeTruthy();
    expect(screen.getByText("1 / 1")).toBeTruthy();
    expect(screen.getByText("/products/BTC-USD/candles")).toBeTruthy();
  });

  it("surfaces stale API state and warning", () => {
    render(<MarketDataFreshness result={result("stale", { ...payload, stale_data_warning: "Provider candle is older than threshold." })} />);
    expect(screen.getByRole("status").textContent).toBe("STALE");
    expect(screen.getByText("Provider candle is older than threshold.")).toBeTruthy();
  });

  it("does not invent freshness when the payload is unavailable", () => {
    render(<MarketDataFreshness result={result("unavailable", null)} />);
    expect(screen.getByText("UNAVAILABLE")).toBeTruthy();
    expect(screen.getByText("Freshness cannot be established.")).toBeTruthy();
  });
});
