export function isMarketsFeatureEnabled(value: string | undefined): boolean {
  return value === "true";
}

export const marketsFeatureEnabled = isMarketsFeatureEnabled(import.meta.env.VITE_CIN_MARKETS_ENABLED);

/** Presentation-only flag; this cannot authenticate the staging backend. */
export function isCoinbaseResearchUiEnabled(value: string | undefined): boolean { return value === "true"; }
export const coinbaseResearchUiEnabled = isCoinbaseResearchUiEnabled(import.meta.env.VITE_CIN_COINBASE_RESEARCH_UI_ENABLED);
