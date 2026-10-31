import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarketComparison } from "./MarketComparison";
import type { CoinbaseCandle } from "../../lib/api";

const candle = (time: number, open: number, close: number): CoinbaseCandle => ({
  open_time: time, close_time: time + 3599, open, high: Math.max(open, close) + 1,
  low: Math.min(open, close) - 1, close, volume: 2,
  open_time_utc: new Date(time * 1000).toISOString(),
  close_time_utc: new Date((time + 3599) * 1000).toISOString(), is_closed: true,
});

describe("Market comparison", () => {
  it("compares percentage performance and identifies relative outperformance", () => {
    render(<MarketComparison primaryProduct="BTC-USD" primaryCandles={[candle(200, 110, 110), candle(100, 100, 110)]} secondaryProduct="ETH-USD" secondaryCandles={[candle(100, 100, 105)]} />);
    expect(screen.getByText("+10.00%")).toBeTruthy();
    expect(screen.getByText("+5.00%")).toBeTruthy();
    expect(screen.getAllByText("+5.00%", { selector: "strong" })).toHaveLength(2);
    expect(screen.getByText("BTC-USD outperformed")).toBeTruthy();
  });

  it("shows unavailable when a series is empty or has a zero baseline", () => {
    render(<MarketComparison primaryProduct="BTC-USD" primaryCandles={[]} secondaryProduct="ETH-USD" secondaryCandles={[candle(100, 0, 2)]} />);
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThanOrEqual(2);
  });

  it("identifies negative relative performance", () => {
    render(<MarketComparison primaryProduct="BTC-USD" primaryCandles={[candle(100, 100, 90)]} secondaryProduct="ETH-USD" secondaryCandles={[candle(100, 100, 105)]} />);
    expect(screen.getByText("ETH-USD outperformed")).toBeTruthy();
    expect(screen.getByText("-15.00%", { selector: "strong" })).toBeTruthy();
  });
});
