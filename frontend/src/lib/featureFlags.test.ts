import { describe, expect, it } from "vitest";
import { isMarketsFeatureEnabled, isCoinbaseResearchUiEnabled } from "./featureFlags";

describe("Markets feature gate", () => {
  it("is disabled when the environment value is absent", () => {
    expect(isMarketsFeatureEnabled(undefined)).toBe(false);
  });
  it("requires the explicit lowercase true value to enable Markets", () => {
    expect(isMarketsFeatureEnabled("false")).toBe(false);
    expect(isMarketsFeatureEnabled("TRUE")).toBe(false);
    expect(isMarketsFeatureEnabled("true")).toBe(true);
  });
});

describe("Coinbase research UI gate",()=>{
  it("requires exact opt-in",()=>{
    expect(isCoinbaseResearchUiEnabled(undefined)).toBe(false);
    expect(isCoinbaseResearchUiEnabled("TRUE")).toBe(false);
    expect(isCoinbaseResearchUiEnabled("1")).toBe(false);
    expect(isCoinbaseResearchUiEnabled("true")).toBe(true);
  });
});
