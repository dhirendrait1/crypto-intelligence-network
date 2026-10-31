import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MarketWatchlist } from "./MarketWatchlist";

describe("Market watchlist", () => {
  it("shows supported pinned markets and marks the selected one", () => {
    render(<MarketWatchlist selectedProduct="BTC-USD" onSelect={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Bitcoin Selected/ }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: /Ethereum View/ })).toBeTruthy();
  });

  it("selects a pinned market without making a data request", () => {
    const onSelect = vi.fn();
    render(<MarketWatchlist selectedProduct="BTC-USD" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /Ethereum View/ }));
    expect(onSelect).toHaveBeenCalledWith("ETH-USD");
  });

  it("allows removing and restoring a pin while retaining at least one", () => {
    render(<MarketWatchlist selectedProduct="BTC-USD" onSelect={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove ETH-USD from watchlist" }));
    expect(screen.queryByRole("button", { name: /Ethereum/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Remove BTC-USD from watchlist" }).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Add ETH-USD to watchlist" }));
    expect(screen.getByRole("button", { name: /Ethereum View/ })).toBeTruthy();
  });

  it("moves selection to a remaining pin when the active market is removed", () => {
    const onSelect = vi.fn();
    render(<MarketWatchlist selectedProduct="BTC-USD" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove BTC-USD from watchlist" }));
    expect(onSelect).toHaveBeenCalledWith("ETH-USD");
  });
});
