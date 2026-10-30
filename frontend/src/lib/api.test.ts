import { afterEach, describe, expect, it, vi } from "vitest";
import { cinApi } from "./api";

describe("CIN API client configuration", () => {
  afterEach(() => vi.unstubAllEnvs());
  it("does not invent a production API origin when no environment URL is supplied", () => {
    expect(cinApi.configured).toBe(false);
  });
});