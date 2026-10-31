import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CandleChart } from "./CandleChart";
import type { CoinbaseCandle } from "../../lib/api";

const candle = (openTime: number, open: number, high: number, low: number, close: number, volume: number): CoinbaseCandle => ({
  open_time: openTime, close_time: openTime + 3599, open, high, low, close, volume,
  open_time_utc: new Date(openTime * 1000).toISOString(),
  close_time_utc: new Date((openTime + 3599) * 1000).toISOString(),
  is_closed: true,
});

describe("CIN candlestick chart", () => {
  it("renders a useful empty state without inventing observations", () => {
    render(<CandleChart candles={[]} productId="BTC-USD" />);
    expect(screen.getByRole("status").textContent).toContain("No candle observations");
  });

  it("renders provider OHLC observations and volume bars accessibly", () => {
    const candles = [candle(200, 100, 112, 96, 108, 30), candle(100, 108, 111, 98, 101, 20)];
    render(<CandleChart candles={candles} productId="BTC-USD" />);
    expect(screen.getByRole("img", { name: /BTC-USD candlestick chart, 2 candles/i })).toBeTruthy();
    expect(document.querySelectorAll("[data-candle-open-time]")).toHaveLength(2);
    expect(document.querySelector('[data-candle-open-time="100"]')).toBeTruthy();
    expect(document.querySelector('[data-candle-open-time="200"]')).toBeTruthy();
    expect(document.querySelectorAll(".volume-bar")).toHaveLength(2);
  });

  it("keeps flat-price ranges finite and renders rising/falling classes", () => {
    render(<CandleChart candles={[candle(100, 50, 50, 50, 50, 0), candle(200, 50, 52, 48, 49, 5)]} productId="ETH-USD" />);
    expect(screen.getByRole("img", { name: /ETH-USD candlestick chart/i })).toBeTruthy();
    expect(document.querySelector(".candle-rising")).toBeTruthy();
    expect(document.querySelector(".candle-falling")).toBeTruthy();
  });
});
