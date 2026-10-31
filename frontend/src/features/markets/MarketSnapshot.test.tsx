import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarketSnapshot } from "./MarketSnapshot";
import type { CoinbaseCandle } from "../../lib/api";

const candle = (time: number, open: number, high: number, low: number, close: number, volume: number): CoinbaseCandle => ({
  open_time: time, close_time: time + 3599, open, high, low, close, volume,
  open_time_utc: new Date(time * 1000).toISOString(),
  close_time_utc: new Date((time + 3599) * 1000).toISOString(),
  is_closed: true,
});

describe("Market snapshot metrics", () => {
  it("shows an explicit unavailable state without candle observations", () => {
    render(<MarketSnapshot candles={[]} productId="BTC-USD" />);
    expect(screen.getByLabelText("Market snapshot").textContent).toContain("Snapshot unavailable");
  });

  it("calculates close, change, high, low and summed volume from sorted observations", () => {
    render(<MarketSnapshot candles={[
      candle(200, 110, 120, 105, 115, 4),
      candle(100, 100, 112, 95, 110, 3),
    ]} productId="BTC-USD" />);
    expect(screen.getByText("$115.00")).toBeTruthy();
    expect(screen.getByText("+$15.00")).toBeTruthy();
    expect(screen.getByText("+15.00% from first open")).toBeTruthy();
    expect(screen.getByText("$120.00")).toBeTruthy();
    expect(screen.getByText("$95.00")).toBeTruthy();
    expect(screen.getByText("7")).toBeTruthy();
  });

  it("handles a zero baseline without producing an infinite percentage", () => {
    render(<MarketSnapshot candles={[candle(100, 0, 5, 0, 4, 1)]} productId="ETH-USD" />);
    expect(screen.getByText("Percentage unavailable (zero baseline)")).toBeTruthy();
    expect(screen.getByText("+$4.00")).toBeTruthy();
  });

  it("labels negative movement distinctly", () => {
    render(<MarketSnapshot candles={[candle(100, 100, 102, 88, 90, 2)]} productId="ETH-USD" />);
    expect(screen.getByText("-$10.00")).toBeTruthy();
    expect(document.querySelector(".snapshot-negative")).toBeTruthy();
  });
});
