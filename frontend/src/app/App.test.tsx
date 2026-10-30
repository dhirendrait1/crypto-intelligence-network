import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import App from "./App";

describe("CIN dashboard shell", () => {
  it("labels preview fixtures and read-only scope", () => {
    render(<App />);
    expect(screen.getByText(/Preview interface — demo mode/i)).toBeTruthy();
    expect(screen.getByText("READ ONLY")).toBeTruthy();
    expect(screen.getByText(/not live market data/i)).toBeTruthy();
  });

  it("navigates to a clearly unimplemented module without fabricating data", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /^Markets$/i }));
    expect(screen.getByRole("heading", { name: "Markets" })).toBeTruthy();
    expect(screen.getByText(/integration pending/i)).toBeTruthy();
    expect(screen.getByText("NOT IMPLEMENTED")).toBeTruthy();
  });
});