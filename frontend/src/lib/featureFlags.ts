export function isMarketsFeatureEnabled(value: string | undefined): boolean {
  return value === "true";
}

export const marketsFeatureEnabled = isMarketsFeatureEnabled(import.meta.env.VITE_CIN_MARKETS_ENABLED);
