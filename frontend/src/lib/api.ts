export type DataState = "fresh" | "stale" | "partial" | "conflicting" | "unavailable" | "unknown" | "error";
export interface ApiResult<T> { state: DataState; data: T | null; retrievedAt: string | null; source: string | null; message: string; }
const API_BASE = (import.meta.env.VITE_CIN_API_BASE_URL ?? "").trim().replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = 12_000;

function classifyError(error: unknown): string {
  if (error instanceof DOMException && error.name === "AbortError") return "Request timed out.";
  if (error instanceof TypeError) return "API is unreachable or browser access is blocked. Check the API URL and CORS policy.";
  return error instanceof Error ? error.message : "Unexpected API error.";
}

async function request<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  if (!API_BASE) return { state: "unavailable", data: null, retrievedAt: null, source: null, message: "API base URL is not configured.", };
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { accept: "application/json", ...init?.headers },
    });
    if (!response.ok) return { state: "error", data: null, retrievedAt: null, source: null, message: `CIN API returned HTTP ${response.status}.` };
    const payload: unknown = await response.json();
    if (!payload || typeof payload !== "object") return { state: "unknown", data: null, retrievedAt: null, source: null, message: "API response did not match the expected object shape." };
    const body = payload as Record<string, unknown>;
    const retrievedAt = typeof body.retrieved_at === "string" ? body.retrieved_at : null;
    const source = typeof body.source === "string" ? body.source : null;
    if (!Array.isArray(body.data)) return { state: "unknown", data: payload as T, retrievedAt, source, message: "Response received, but its data collection is missing or has an unsupported shape." };
    const rows = body.data as unknown[];
    const rowStates = rows.map((row) => row && typeof row === "object" ? (row as Record<string, unknown>).freshness_status : undefined);
    const hasStale = rowStates.includes("stale") || body.data_mode === "stale_cache";
    const hasUnknown = rowStates.includes("unknown");
    const hasFresh = rowStates.includes("fresh");
    const state: DataState = body.partial_result === true || Array.isArray(body.missing_coins) && body.missing_coins.length > 0
      ? "partial" : hasStale ? "stale" : hasUnknown || !hasFresh && rows.length > 0 ? "unknown" : rows.length === 0 ? "unavailable" : "fresh";
    return { state, data: payload as T, retrievedAt, source, message: state === "fresh" ? "Provider timestamp indicates fresh data." : state === "partial" ? "Some requested records are missing." : state === "stale" ? "Cached or stale observations are present; do not treat them as current." : state === "unknown" ? "Freshness cannot be established from the response." : "No usable records were returned." };
  } catch (error) {
    return { state: "error", data: null, retrievedAt: null, source: null, message: classifyError(error) };
  } finally {
    clearTimeout(timeout);
  }
}

export const cinApi = {
  configured: Boolean(API_BASE),
  getHealth() { return request<Record<string, unknown>>("/health"); },
  getReadiness() { return request<Record<string, unknown>>("/ready"); },
};