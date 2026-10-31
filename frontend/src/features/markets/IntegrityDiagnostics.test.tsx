import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { IntegrityDiagnostics } from "./IntegrityDiagnostics";
import type { ApiResult, CoinbaseCandlesResponse } from "../../lib/api";

const candle = {
  open_time: 100, close_time: 159, open: 10, high: 12, low: 9, close: 11,
  volume: 5, open_time_utc: "1970-01-01T00:01:40Z",
  close_time_utc: "1970-01-01T00:02:39Z", is_closed: true,
};

const result: ApiResult<CoinbaseCandlesResponse> = {
  state: "fresh", retrievedAt: "1970-01-01T00:03:00Z", source: "coinbase_exchange_public",
  message: "accepted",
  data: {
    service: "cin", mode: "read_only", source: "coinbase_exchange_public",
    source_endpoint: "/products/BTC-USD/candles", product_id: "BTC-USD", quote_currency: "USD",
    granularity: "1m", requested_start_utc: "1970-01-01T00:01:40Z",
    requested_end_utc: "1970-01-01T00:03:00Z", retrieved_at: "1970-01-01T00:03:00Z",
    count: 1, provider_rows_received: 1, provider_rows_invalid: 0, provider_rows_duplicate: 0, provider_rows_valid_before_deduplication: 1, normalized_rows_count: 1, provider_window_coverage: "not_established", latest_closed_candle_close_time_utc: "2026-10-31T00:00:59Z",
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

  it("reports provider row accounting and keeps requested-window coverage unestablished", () => {
    const accounted = {
      ...result,
      data: { ...result.data!, provider_rows_received: 4, provider_rows_invalid: 1, provider_rows_duplicate: 1, provider_rows_valid_before_deduplication: 3, normalized_rows_count: 2 },
    };
    render(<IntegrityDiagnostics result={accounted} />);
    expect(screen.getByText("Received 4; invalid 1; duplicate 1; normalized 2.")).toBeTruthy();
    expect(screen.getByText("The provider response does not establish complete coverage of the requested time window.")).toBeTruthy();
    expect(screen.getAllByText("WARN").length).toBeGreaterThan(0);
    expect(screen.getAllByText("UNAVAILABLE").length).toBeGreaterThan(0);
  });

  it("warns when provider row accounting contains negative counters", () => {
    const malformed = {
      ...result,
      data: { ...result.data!, provider_rows_received: -1, provider_rows_invalid: -1, provider_rows_duplicate: 0, provider_rows_valid_before_deduplication: 0, normalized_rows_count: 0, count: 0, data: [] },
    };
    render(<IntegrityDiagnostics result={malformed} />);
    expect(screen.getByText("Received -1; invalid -1; duplicate 0; normalized 0.")).toBeTruthy();
    const accountingRow = screen.getByText("Provider row accounting").closest("li");
    expect(accountingRow?.querySelector(".integrity-check-warn")).toBeTruthy();
    expect(accountingRow?.querySelector(".integrity-check-pass")).toBeNull();
  });

  it("classifies stale accepted data as a warning without calling it malformed", () => {
    render(<IntegrityDiagnostics result={{ ...result, state: "stale", message: "Provider data is stale." }} />);
    expect(screen.getByText("Response state: stale. Provider data is stale.")).toBeTruthy();
    expect(screen.getAllByText("WARN").length).toBeGreaterThan(0);
  });

  it("surfaces contract rejection separately when no validated payload is available", () => {
    render(<IntegrityDiagnostics result={{ ...result, data: null, state: "unknown", message: "Candle timestamps do not match." }} />);
    expect(screen.getByText("Response state: unknown. Candle timestamps do not match.")).toBeTruthy();
  });

  it("does not infer integrity when no validated payload exists", () => {
    render(<IntegrityDiagnostics result={{ ...result, data: null, state: "unknown" }} />);
    expect(screen.getByText("No validated candle payload is available.")).toBeTruthy();
    expect(screen.getAllByText("UNAVAILABLE").length).toBe(14);
    expect(screen.queryByText("PASS")).toBeNull();
  });

  it("does not report candle-level checks as passed for an empty response", () => {
    const empty = {
      ...result,
      data: { ...result.data!, count: 0, data: [] },
    };
    render(<IntegrityDiagnostics result={empty} />);
    expect(screen.getByText("No candle rows are available to inspect.")).toBeTruthy();
    expect(screen.getAllByText("UNAVAILABLE").length).toBe(10);
  });

  it("passes requested-window bounds when every candle open is inside the requested range", () => {
    render(<IntegrityDiagnostics result={result} />);
    const row = screen.getByText("Requested-window candle bounds").closest("li");
    expect(row?.querySelector(".integrity-check-pass")).toBeTruthy();
  });

  it("warns when a returned candle open falls outside the requested window", () => {
    const outsideWindow = {
      ...result,
      data: { ...result.data!, data: [{ ...candle, open_time: 99 }] },
    };
    render(<IntegrityDiagnostics result={outsideWindow} />);
    const row = screen.getByText("Requested-window candle bounds").closest("li");
    expect(row?.querySelector(".integrity-check-warn")).toBeTruthy();
  });

  it("passes candle interval range when close time matches the interval boundary", () => {
    render(<IntegrityDiagnostics result={result} />);
    const row = screen.getByText("Candle interval range").closest("li");
    expect(row?.querySelector(".integrity-check-pass")).toBeTruthy();
  });

  it("warns when candle close time does not match the expected interval boundary", () => {
    const incorrectRange = {
      ...result,
      data: { ...result.data!, data: [{ ...candle, close_time: 158 }] },
    };
    render(<IntegrityDiagnostics result={incorrectRange} />);
    const row = screen.getByText("Candle interval range").closest("li");
    expect(row?.querySelector(".integrity-check-warn")).toBeTruthy();
  });

  it("warns about missing intervals between returned candles without rejecting the payload", () => {
    const withGap = {
      ...result,
      data: { ...result.data!, data: [
        { ...candle, open_time: 0, close_time: 59 },
        { ...candle, open_time: 180, close_time: 239 },
      ], count: 2 },
    };
    render(<IntegrityDiagnostics result={withGap} />);
    expect(screen.getByText("2 expected interval(s) missing across 1 gap(s) between returned candles. Edge coverage is not inferred.")).toBeTruthy();
    expect(screen.getAllByText("WARN").length).toBeGreaterThan(0);
  });

  it("warns when returned candles repeat an open timestamp", () => {
    const duplicated = {
      ...result,
      data: { ...result.data!, data: [
        { ...candle, open_time: 0, close_time: 59 },
        { ...candle, open_time: 0, close_time: 59 },
      ], count: 2 },
    };
    render(<IntegrityDiagnostics result={duplicated} />);
    expect(screen.getByText("One or more candle timestamps are duplicated or out of chronological order.")).toBeTruthy();
  });

  it("does not round irregular timestamp deltas into a false missing-interval count", () => {
    const irregular = {
      ...result,
      data: { ...result.data!, data: [
        { ...candle, open_time: 0, close_time: 59 },
        { ...candle, open_time: 90, close_time: 149 },
      ], count: 2 },
    };
    render(<IntegrityDiagnostics result={irregular} />);
    expect(screen.getByText("One or more candle open timestamps are not aligned to the UTC interval boundary.")).toBeTruthy();
    expect(screen.getByText("1 transition(s) do not follow an exact interval multiple; missing-slot count is not inferred for those transitions.")).toBeTruthy();
  });

  it("passes continuity when returned candles are consecutive", () => {
    const consecutive = {
      ...result,
      data: { ...result.data!, data: [
        { ...candle, open_time: 0, close_time: 59 },
        { ...candle, open_time: 60, close_time: 119 },
      ], count: 2 },
    };
    render(<IntegrityDiagnostics result={consecutive} />);
    expect(screen.getByText("No missing intervals detected between the first and last returned candles. Edge coverage is not inferred.")).toBeTruthy();
  });

  it("passes when numeric candle epochs match their UTC timestamp strings", () => {
    render(<IntegrityDiagnostics result={result} />);
    const row = screen.getByText("Epoch/UTC timestamp consistency").closest("li");
    expect(row?.querySelector(".integrity-check-pass")).toBeTruthy();
  });

  it("warns when numeric candle epochs disagree with UTC timestamp strings", () => {
    const mismatched = {
      ...result,
      data: { ...result.data!, data: [{ ...candle, open_time_utc: "1970-01-01T00:01:41Z" }] },
    };
    render(<IntegrityDiagnostics result={mismatched} />);
    const row = screen.getByText("Epoch/UTC timestamp consistency").closest("li");
    expect(row?.querySelector(".integrity-check-warn")).toBeTruthy();
  });

  it("warns when is_closed disagrees with close time and retrieval time", () => {
    const mismatched = {
      ...result,
      data: { ...result.data!, data: [{ ...candle, close_time: 300, is_closed: true }] },
    };
    render(<IntegrityDiagnostics result={mismatched} />);
    const row = screen.getByText("Candle close-state consistency").closest("li");
    expect(row?.querySelector(".integrity-check-warn")).toBeTruthy();
  });

  it("warns when candle OHLCV values are non-finite", () => {
    const malformed = {
      ...result,
      data: { ...result.data!, data: [{ ...candle, high: Number.NaN }] },
    };
    render(<IntegrityDiagnostics result={malformed} />);
    expect(screen.getByText("One or more candles contain non-finite values or violate OHLC/volume bounds.")).toBeTruthy();
    const boundsRow = screen.getByText("OHLC and volume bounds").closest("li");
    expect(boundsRow?.querySelector(".integrity-check-warn")).toBeTruthy();
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
    expect(screen.getByText("One or more candle timestamps are duplicated or out of chronological order.")).toBeTruthy();
    expect(screen.getByText("One or more candles contain non-finite values or violate OHLC/volume bounds.")).toBeTruthy();
    expect(screen.getByText("One or more candle timestamps are invalid.")).toBeTruthy();
  });
});

  it("keeps requested-window coverage unavailable even when all returned candles are within bounds", () => {
    render(<IntegrityDiagnostics result={result} />);
    const boundsRow = screen.getByText("Requested-window candle bounds").closest("li");
    const coverageRow = screen.getByText("Requested-window coverage").closest("li");
    expect(boundsRow?.querySelector(".integrity-check-pass")).toBeTruthy();
    expect(coverageRow?.querySelector(".integrity-check-unavailable")).toBeTruthy();
    expect(screen.getByText("The provider response does not establish complete coverage of the requested time window.")).toBeTruthy();
  });

  it("accepts candle opens exactly at either requested-window boundary", () => {
    const atStart = { ...candle, open_time: 100, close_time: 159 };
    const atEnd = { ...candle, open_time: 180, close_time: 239 };
    const boundaryResult = {
      ...result,
      data: {
        ...result.data!,
        requested_start_utc: "1970-01-01T00:01:40Z",
        requested_end_utc: "1970-01-01T00:03:00Z",
        data: [atStart, atEnd],
        count: 2,
        provider_rows_received: 2,
        provider_rows_invalid: 0,
        provider_rows_duplicate: 0,
        provider_rows_valid_before_deduplication: 2,
        normalized_rows_count: 2,
      },
    };
    render(<IntegrityDiagnostics result={boundaryResult} />);
    const row = screen.getByText("Requested-window candle bounds").closest("li");
    expect(row?.querySelector(".integrity-check-pass")).toBeTruthy();
  });

  it("does not claim requested-window bounds pass when the request range is reversed", () => {
    const reversedWindow = {
      ...result,
      data: {
        ...result.data!,
        requested_start_utc: "1970-01-01T00:03:00Z",
        requested_end_utc: "1970-01-01T00:01:40Z",
      },
    };
    render(<IntegrityDiagnostics result={reversedWindow} />);
    const row = screen.getByText("Requested-window candle bounds").closest("li");
    expect(row?.querySelector(".integrity-check-unavailable")).toBeTruthy();
  });
