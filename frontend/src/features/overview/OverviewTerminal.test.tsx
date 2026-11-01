import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { OverviewTerminal } from "./OverviewTerminal";

describe("CIN video-reference overview", () => {
  it("keeps every unverified market metric explicitly unknown", () => {
    render(<OverviewTerminal health={null} readiness={null} />);
    expect(screen.getByRole("heading", { name: "Neural intelligence network" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Provider provenance ledger" })).toBeTruthy();
    expect(screen.getAllByText(/Price unverified/).length).toBe(2);
    expect(screen.getByText("NO CANDLES")).toBeTruthy();
    expect(screen.getAllByText("NOT LOADED").length).toBe(4);
    expect(screen.queryByText("$98,919")).toBeNull();
  });

  it("offers an accessible pause control without touching market endpoints", () => {
    render(<OverviewTerminal health={null} readiness={null} />);
    const pause = screen.getByRole("button", { name: "Pause motion" });
    expect(pause.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(pause);
    const resume = screen.getByRole("button", { name: "Resume motion" });
    expect(resume.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(resume);
    expect(screen.getByRole("button", { name: "Pause motion" })).toBeTruthy();
  });

  it("maintains an explicit read-only research boundary", () => {
    render(<OverviewTerminal health={null} readiness={null} />);
    expect(screen.getByText(/NO TRADING · NO ORDERS · NO WALLETS/)).toBeTruthy();
    expect(screen.getByText(/visualization only/i)).toBeTruthy();
    expect(screen.getByText(/no production activation/i)).toBeTruthy();
  });
});
