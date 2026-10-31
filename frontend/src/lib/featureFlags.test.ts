import { describe, expect, it } from "vitest";
import { isMarketsFeatureEnabled } from "./featureFlags";

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
