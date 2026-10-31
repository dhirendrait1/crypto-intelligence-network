import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { IntegrityDiagnostics } from "./IntegrityDiagnostics";
import type { ApiResult, CoinbaseCandlesResponse } from "../../lib/api";

const candle = {
  open_time: 100, close_time: 159, open: 10, high: 12, low: 9, close: 11,
  volume: 5, open_time_utc: "2026-10-31T00:00:00Z",
  close_time_utc: "2026-10-31T00:00:59Z", is_closed: true,
};

const result: ApiResult<CoinbaseCandlesResponse> = {
  state: "fresh", retrievedAt: "2026-10-31T00:01:00Z", source: "coinbase_exchange_public",
  message: "accepted",
  data: {
    service: "cin", mode: "read_only", source: "coinbase_exchange_public",
    source_endpoint: "/products/BTC-USD/candles", product_id: "BTC-USD", quote_currency: "USD",
    granularity: "1m", requested_start_utc: "2026-10-31T00:00:00Z",
    requested_end_utc: "2026-10-31T00:01:00Z", retrieved_at: "2026-10-31T00:01:00Z",
    count: 1, latest_closed_candle_close_time_utc: "2026-10-31T00:00:59Z",
    latest_closed_candle_age_seconds: 1, stale_threshold_seconds: 300,
    stale_data_warning: null, data: [candle], limitations: [],
  },
};

describe("Integrity diagnostics", () => {
  it("reports structural checks for an accepted candle payload", () => {
    render(<IntegrityDiagnostics result={result} />);
    expect(screen.getByText("Chronological ordering")).toBeTruthy();
    expect(screen.getByText("OHLC and volume bounds")).toBeTruthy();
    expect(screen.getByText("1 returned / 1 declared")).toBeTruthy();
  });

  it("does not infer integrity when no validated payload exists", () => {
    render(<IntegrityDiagnostics result={{ ...result, data: null, state: "unknown" }} />);
    expect(screen.getByText("No validated candle payload is available.")).toBeTruthy();
    expect(screen.getAllByText("UNAVAILABLE").length).toBe(5);
  });

  it("does not report candle-level checks as passed for an empty response", () => {
    const empty = {
      ...result,
      data: { ...result.data!, count: 0, data: [] },
    };
    render(<IntegrityDiagnostics result={empty} />);
    expect(screen.getByText("No candle rows are available to inspect.")).toBeTruthy();
    expect(screen.getAllByText("UNAVAILABLE").length).toBe(3);
  });

  it("warns when candle OHLCV values are non-finite", () => {
    const malformed = {
      ...result,
      data: { ...result.data!, data: [{ ...candle, high: Number.NaN }] },
    };
    render(<IntegrityDiagnostics result={malformed} />);
    expect(screen.getByText("One or more candles contain non-finite values or violate OHLC/volume bounds.")).toBeTruthy();
    expect(screen.getByText("WARN")).toBeTruthy();
  });

  it("detects count, ordering, bounds, and timestamp inconsistencies independently", () => {
    const malformed = {
      ...result,
      data: {
        ...result.data!,
        count: 1,
        data: [
          candle,
          {
            ...candle,
            open_time: 90,
            close_time: 89,
            volume: -1,
            open_time_utc: "not-a-date",
            close_time_utc: "also-not-a-date",
          },
        ],
      },
    };
    render(<IntegrityDiagnostics result={malformed} />);
    expect(screen.getByText("2 returned / 1 declared")).toBeTruthy();
    expect(screen.getByText("One or more candles are out of chronological order.")).toBeTruthy();
    expect(screen.getByText("One or more candles contain non-finite values or violate OHLC/volume bounds.")).toBeTruthy();
    expect(screen.getByText("One or more candle timestamps are invalid.")).toBeTruthy();
  });
});
