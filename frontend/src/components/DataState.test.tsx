import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataStateBadge, DataStatePanel } from "./DataState";

describe("data-state presentation", () => {
  it("distinguishes stale observations from fresh observations", () => {
    render(<><DataStateBadge state="stale" /><DataStateBadge state="fresh" /></>);
    expect(screen.getByText("STALE")).toBeTruthy();
    expect(screen.getByText("FRESH")).toBeTruthy();
  });
  it("shows provenance and retrieval time when supplied", () => {
    render(<DataStatePanel state="partial" message="Some records are missing." source="Provider X" retrievedAt="2026-10-31T00:00:00Z" />);
    expect(screen.getByText("Provider X")).toBeTruthy();
    expect(screen.getByText(/2026-10-31/)).toBeTruthy();
  });
});