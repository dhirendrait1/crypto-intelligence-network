import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import App from "./App";

describe("CIN dashboard shell", () => {
  it("labels preview fixtures and read-only scope", () => {
    render(<App />);
    expect(screen.getByText(/Preview interface — demo mode/i)).toBeTruthy();
    expect(screen.getByText("READ ONLY")).toBeTruthy();
    expect(screen.getByText(/overview cards are layout fixtures/i)).toBeTruthy();
  });

  it("keeps Markets out of navigation while its feature gate is disabled", () => {
    render(<App />);
    expect(screen.queryByRole("button", { name: /^Markets$/i })).toBeNull();
    expect(screen.getByRole("heading", { name: "Overview" })).toBeTruthy();
  });

  it("navigates to a clearly unimplemented module without fabricating data", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /^Screening$/i }));
    expect(screen.getByRole("heading", { name: "Screening" })).toBeTruthy();
    expect(screen.getByText(/integration pending/i)).toBeTruthy();
    expect(screen.getByText("NOT IMPLEMENTED")).toBeTruthy();
  });
});
