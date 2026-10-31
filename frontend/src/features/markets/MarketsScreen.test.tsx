import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { cinApi } from "../../lib/api";
import { MarketsScreen } from "./MarketsScreen";

vi.mock("../../lib/api", () => ({
  cinApi: { getCoinbaseCandles: vi.fn() },
}));

const response = {
  state: "fresh" as const,
  retrievedAt: "2026-10-31T00:00:00Z",
  source: "coinbase_exchange_public",
  message: "Contract passed.",
  data: {
    service: "cin" as const, mode: "read_only" as const, source: "coinbase_exchange_public",
    source_endpoint: "/products/BTC-USD/candles", product_id: "BTC-USD", quote_currency: "USD" as const,
    granularity: "1h", requested_start_utc: "2026-10-30T00:00:00Z", requested_end_utc: "2026-10-31T00:00:00Z",
    retrieved_at: "2026-10-31T00:00:00Z", count: 1, latest_closed_candle_close_time_utc: "2026-10-30T23:00:00Z",
    latest_closed_candle_age_seconds: 3600, stale_threshold_seconds: 7200, stale_data_warning: null,
    data: [{ open_time: 1793401200, close_time: 1793404799, open: 100, high: 110, low: 95, close: 105, volume: 12,
      open_time_utc: "2026-10-30T23:00:00Z", close_time_utc: "2026-10-30T23:59:59Z", is_closed: true }],
    limitations: [],
  },
};

describe("Markets screen", () => {
  beforeEach(() => vi.clearAllMocks());
  it("does not request market data until the user activates Load candles", () => {
    render(<MarketsScreen />);
    expect(screen.getByText("No market request made")).toBeTruthy();
    expect(cinApi.getCoinbaseCandles).not.toHaveBeenCalled();
  });
  it("loads public candles on demand and displays state and provenance", async () => {
    vi.mocked(cinApi.getCoinbaseCandles).mockResolvedValue(response);
    render(<MarketsScreen />);
    fireEvent.click(screen.getByRole("button", { name: "Load candles" }));
    await waitFor(() => expect(cinApi.getCoinbaseCandles).toHaveBeenCalledTimes(1));
    expect(cinApi.getCoinbaseCandles).toHaveBeenCalledWith("BTC-USD", "1h", expect.any(Number), expect.any(Number));
    expect(await screen.findAllByText("FRESH")).toHaveLength(3);
    expect(screen.getByText("Session quality history")).toBeTruthy();
    expect(screen.getByText("Source: coinbase_exchange_public")).toBeTruthy();
    expect(screen.getByText("105")).toBeTruthy();
    expect(screen.getByText(/No order placement, trade execution/i)).toBeTruthy();
  });

  it("locks market, interval, comparison, and watchlist controls during a candle request", async () => {
    let resolveRequest!: (value: typeof response) => void;
    vi.mocked(cinApi.getCoinbaseCandles).mockReturnValue(
      new Promise((resolve) => { resolveRequest = resolve; }),
    );
    render(<MarketsScreen />);
    fireEvent.click(screen.getByRole("button", { name: "Load candles" }));

    expect((screen.getByRole("combobox", { name: "Market" }) as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByRole("combobox", { name: "Interval" }) as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Loading…" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Load comparison" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: /Bitcoin/ }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: /Ethereum/ }) as HTMLButtonElement).disabled).toBe(true);

    resolveRequest(response);
    await waitFor(() => expect((screen.getByRole("button", { name: "Load candles" }) as HTMLButtonElement).disabled).toBe(false));
    expect((screen.getByRole("combobox", { name: "Market" }) as HTMLSelectElement).disabled).toBe(false);
    expect((screen.getByRole("combobox", { name: "Interval" }) as HTMLSelectElement).disabled).toBe(false);
  });


  it("locks market and candle controls during a comparison request", async () => {
    const resolveRequests: Array<(value: typeof response) => void> = [];
    vi.mocked(cinApi.getCoinbaseCandles).mockImplementation(
      () => new Promise((resolve) => { resolveRequests.push(resolve); }),
    );
    render(<MarketsScreen />);
    fireEvent.click(screen.getByRole("button", { name: "Load comparison" }));

    expect(cinApi.getCoinbaseCandles).toHaveBeenCalledTimes(2);
    expect((screen.getByRole("combobox", { name: "Market" }) as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByRole("combobox", { name: "Interval" }) as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Load candles" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Comparing…" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: /Bitcoin/ }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: /Ethereum/ }) as HTMLButtonElement).disabled).toBe(true);

    resolveRequests.forEach((resolve) => resolve(response));
    await waitFor(() => expect((screen.getByRole("button", { name: "Load comparison" }) as HTMLButtonElement).disabled).toBe(false));
    expect((screen.getByRole("combobox", { name: "Market" }) as HTMLSelectElement).disabled).toBe(false);
    expect((screen.getByRole("combobox", { name: "Interval" }) as HTMLSelectElement).disabled).toBe(false);
  });

});
