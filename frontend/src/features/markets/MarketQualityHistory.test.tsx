import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarketQualityHistory, type MarketQualityObservation } from "./MarketQualityHistory";

const observation: MarketQualityObservation = {
  id: "one", productId: "BTC-USD", granularity: "1h", state: "fresh",
  observedAt: "2026-10-31T00:00:00Z", source: "Coinbase Exchange",
  candleCount: 24, integrity: "Contract accepted",
};

describe("Market quality history", () => {
  it("shows an empty session state before manual observations", () => {
    render(<MarketQualityHistory observations={[]} />);
    expect(screen.getByText(/No observations recorded in this screen session/)).toBeTruthy();
  });

  it("lists real observation metadata and explains session-only retention", () => {
    render(<MarketQualityHistory observations={[observation]} />);
    expect(screen.getByText("BTC-USD")).toBeTruthy();
    expect(screen.getByText("24")).toBeTruthy();
    expect(screen.getByText("Contract accepted")).toBeTruthy();
    expect(screen.getByText(/not persisted or an uptime statistic/)).toBeTruthy();
  });
});
