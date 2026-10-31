export type DataState = "fresh" | "stale" | "partial" | "conflicting" | "unavailable" | "unknown" | "error";
export interface ApiResult<T> { state: DataState; data: T | null; retrievedAt: string | null; source: string | null; message: string; }
export interface CoinbaseCandle {
  open_time: number;
  close_time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  open_time_utc: string;
  close_time_utc: string;
  is_closed: boolean;
}
export interface CoinbaseCandlesResponse {
  service: "cin";
  mode: "read_only";
  source: string;
  source_endpoint: string;
  product_id: string;
  quote_currency: "USD";
  granularity: string;
  requested_start_utc: string;
  requested_end_utc: string;
  retrieved_at: string;
  count: number;
  latest_closed_candle_close_time_utc: string | null;
  latest_closed_candle_age_seconds: number | null;
  stale_threshold_seconds: number;
  stale_data_warning: string | null;
  data: CoinbaseCandle[];
  limitations: string[];
}
const API_BASE = (import.meta.env.VITE_CIN_API_BASE_URL ?? "").trim().replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = 12_000;

function classifyError(error: unknown): string {
  if (error instanceof DOMException && error.name === "AbortError") return "Request timed out.";
  if (error instanceof TypeError) return "API is unreachable or browser access is blocked. Check the API URL and CORS policy.";
  return error instanceof Error ? error.message : "Unexpected API error.";
}

function isIsoTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && Number.isFinite(Date.parse(value));
}

export function validateCoinbaseCandlesPayload(
  payload: unknown,
  expectedProductId: string,
  expectedGranularity: string,
  expectedStart?: number,
  expectedEnd?: number,
): { valid: boolean; message: string } {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return { valid: false, message: "Response must be a JSON object." };
  const body = payload as Record<string, unknown>;
  if (body.service !== "cin" || body.mode !== "read_only") return { valid: false, message: "Response is not identified as CIN read-only data." };
  if (body.product_id !== expectedProductId || body.quote_currency !== "USD") return { valid: false, message: "Product or USD quote does not match the requested market." };
  if (body.granularity !== expectedGranularity) return { valid: false, message: "Candle interval does not match the requested interval." };
  if (typeof body.source !== "string" || !body.source.trim() || !isIsoTimestamp(body.retrieved_at)) return { valid: false, message: "Source provenance or retrieval timestamp is missing." };
  if (!Array.isArray(body.data) || !Number.isInteger(body.count) || body.count !== body.data.length) return { valid: false, message: "Candle count does not match the returned data collection." };
  if (typeof body.stale_data_warning !== "string" && body.stale_data_warning !== null) return { valid: false, message: "Staleness metadata has an unsupported shape." };
  if (!isIsoTimestamp(body.requested_start_utc) || !isIsoTimestamp(body.requested_end_utc)) return { valid: false, message: "Requested candle window must contain valid UTC timestamps." };
  const requestedStart = Date.parse(body.requested_start_utc as string) / 1000;
  const requestedEnd = Date.parse(body.requested_end_utc as string) / 1000;
  const intervalSeconds: Record<string, number> = { "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400 };
  const expectedIntervalSeconds = intervalSeconds[expectedGranularity];
  if (expectedIntervalSeconds === undefined) return { valid: false, message: "Requested candle interval is not supported by the frontend contract." };
  if (requestedStart > requestedEnd) return { valid: false, message: "Requested candle window starts after it ends." };
  if ((expectedStart !== undefined && requestedStart !== expectedStart) || (expectedEnd !== undefined && requestedEnd !== expectedEnd)) {
    return { valid: false, message: "Response request window does not match the client request parameters." };
  }
  let previousOpenTime = -Infinity;
  for (const [index, item] of body.data.entries()) {
    if (!item || typeof item !== "object" || Array.isArray(item)) return { valid: false, message: `Candle ${index + 1} is not an object.` };
    const candle = item as Record<string, unknown>;
    const numeric = ["open_time", "close_time", "open", "high", "low", "close", "volume"] as const;
    if (numeric.some((key) => typeof candle[key] !== "number" || !Number.isFinite(candle[key]))) return { valid: false, message: `Candle ${index + 1} contains a non-finite numeric field.` };
    const openTime = candle.open_time as number, closeTime = candle.close_time as number;
    if (openTime < requestedStart || openTime > requestedEnd) return { valid: false, message: `Candle ${index + 1} open timestamp falls outside the requested UTC window.` };
    if (openTime % expectedIntervalSeconds !== 0) return { valid: false, message: `Candle ${index + 1} open timestamp is not aligned to the requested interval boundary.` };
    const open = candle.open as number, high = candle.high as number, low = candle.low as number, close = candle.close as number, volume = candle.volume as number;
    if (closeTime < openTime || openTime <= previousOpenTime || volume < 0 || low > high || low > open || open > high || low > close || close > high) {
      return { valid: false, message: `Candle ${index + 1} failed OHLC, volume, or chronological validation. Candle open timestamps must be strictly increasing with no duplicates.` };
    }
    if (!isIsoTimestamp(candle.open_time_utc) || !isIsoTimestamp(candle.close_time_utc) || typeof candle.is_closed !== "boolean") {
      return { valid: false, message: `Candle ${index + 1} has invalid timestamps or close-state metadata.` };
    }
    if (Date.parse(candle.open_time_utc as string) / 1000 !== openTime || Date.parse(candle.close_time_utc as string) / 1000 !== closeTime) {
      return { valid: false, message: `Candle ${index + 1} UTC timestamps do not match their numeric epoch fields.` };
    }
    previousOpenTime = openTime;
  }
  return { valid: true, message: "Coinbase public USD candles passed the frontend response contract." };
}

async function request<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  if (!API_BASE) return { state: "unavailable", data: null, retrievedAt: null, source: null, message: "API base URL is not configured." };
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
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) return { state: "unknown", data: null, retrievedAt: null, source: null, message: "API response did not match the expected object shape." };
    const body = payload as Record<string, unknown>;
    const retrievedAt = typeof body.retrieved_at === "string" ? body.retrieved_at : null;
    const source = typeof body.source === "string" ? body.source : null;
    if (path === "/health" || path === "/ready") {
      const healthy = body.status === "ok" || body.status === "ready";
      return { state: healthy ? "fresh" : "unavailable", data: payload as T, retrievedAt, source, message: healthy ? "CIN service endpoint responded successfully." : "CIN service did not report a healthy state." };
    }
    if (path.startsWith("/coinbase/market-candles")) {
      const params = new URLSearchParams(path.split("?")[1] ?? "");
      const expectedStart = Number(params.get("start"));
      const expectedEnd = Number(params.get("end"));
      const contract = validateCoinbaseCandlesPayload(
        payload,
        params.get("product_id") ?? "",
        params.get("granularity") ?? "",
        Number.isFinite(expectedStart) ? expectedStart : undefined,
        Number.isFinite(expectedEnd) ? expectedEnd : undefined,
      );
      if (!contract.valid) return { state: "unknown", data: null, retrievedAt, source, message: contract.message };
      const stale = typeof body.stale_data_warning === "string" && body.stale_data_warning.length > 0;
      return { state: stale ? "stale" : "fresh", data: payload as T, retrievedAt, source, message: stale ? body.stale_data_warning as string : contract.message };
    }
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
  getCoinbaseCandles(productId: string, granularity: "1m" | "5m" | "15m" | "1h" | "6h" | "1d", start: number, end: number) {
    const query = new URLSearchParams({ product_id: productId, granularity, start: String(start), end: String(end) });
    return request<CoinbaseCandlesResponse>(`/coinbase/market-candles?${query.toString()}`);
  },
};
