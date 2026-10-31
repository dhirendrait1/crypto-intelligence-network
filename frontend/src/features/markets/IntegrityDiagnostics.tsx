import type { ApiResult, CoinbaseCandlesResponse } from "../../lib/api";

interface IntegrityDiagnosticsProps {
  result: ApiResult<CoinbaseCandlesResponse>;
}

type CheckState = "PASS" | "WARN" | "UNAVAILABLE";

interface Diagnostic {
  label: string;
  state: CheckState;
  detail: string;
}

export function IntegrityDiagnostics({ result }: IntegrityDiagnosticsProps) {
  const payload = result.data;
  const candles = payload?.data ?? [];
  const hasPayload = payload !== null;
  const hasCandles = hasPayload && candles.length > 0;
  const chronological = candles.every((candle, index) =>
    Number.isFinite(candle.open_time) &&
    Number.isFinite(candle.close_time) &&
    (index === 0 || candle.open_time >= candles[index - 1].open_time)
  );
  const ohlcValid = candles.every((candle) =>
    [candle.open, candle.high, candle.low, candle.close, candle.volume].every(Number.isFinite) &&
    candle.close_time >= candle.open_time &&
    candle.volume >= 0 &&
    candle.low <= candle.high &&
    candle.low <= candle.open && candle.open <= candle.high &&
    candle.low <= candle.close && candle.close <= candle.high
  );
  const timestampsValid = candles.every((candle) =>
    Number.isFinite(Date.parse(candle.open_time_utc)) &&
    Number.isFinite(Date.parse(candle.close_time_utc))
  );
  const countMatches = payload !== null && payload.count === candles.length;
  const providerAccountingAvailable = payload !== null &&
    Number.isInteger(payload.provider_rows_received) && payload.provider_rows_received! >= 0 &&
    Number.isInteger(payload.provider_rows_invalid) && payload.provider_rows_invalid! >= 0 &&
    Number.isInteger(payload.provider_rows_duplicate) && payload.provider_rows_duplicate! >= 0 &&
    Number.isInteger(payload.provider_rows_valid_before_deduplication) && payload.provider_rows_valid_before_deduplication! >= 0 &&
    Number.isInteger(payload.normalized_rows_count) && payload.normalized_rows_count! >= 0;
  const providerAccountingConsistent = providerAccountingAvailable &&
    payload.provider_rows_received === payload.provider_rows_invalid! + payload.provider_rows_valid_before_deduplication! &&
    payload.provider_rows_duplicate! <= payload.provider_rows_valid_before_deduplication! &&
    payload.normalized_rows_count === payload.provider_rows_valid_before_deduplication! - payload.provider_rows_duplicate! &&
    payload.normalized_rows_count === payload.count;
  const intervalSeconds: Record<string, number> = { "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400 };
  const interval = payload ? intervalSeconds[payload.granularity] : undefined;
  const missingIntervals = interval && candles.length > 1
    ? candles.slice(1).reduce((total, candle, index) => {
      const delta = candle.open_time - candles[index].open_time;
      return total + (delta > interval ? Math.max(0, Math.round(delta / interval) - 1) : 0);
    }, 0)
    : 0;
  const gapCount = interval && candles.length > 1
    ? candles.slice(1).filter((candle, index) => candle.open_time - candles[index].open_time > interval).length
    : 0;


  const checks: Diagnostic[] = [
    { label: "Response contract", state: hasPayload ? "PASS" : "UNAVAILABLE", detail: hasPayload ? "The frontend API contract accepted this payload." : "No validated candle payload is available." },
    { label: "API response classification", state: result.state === "fresh" ? "PASS" : result.state === "stale" || result.state === "partial" || result.state === "conflicting" ? "WARN" : "UNAVAILABLE", detail: `Response state: ${result.state}. ${result.message}` },
    { label: "Declared candle count", state: hasPayload ? countMatches ? "PASS" : "WARN" : "UNAVAILABLE", detail: hasPayload ? `${candles.length} returned / ${payload.count} declared` : "Cannot compare counts without a payload." },
    { label: "Provider row accounting", state: !hasPayload || !providerAccountingAvailable ? "UNAVAILABLE" : !providerAccountingConsistent || payload.provider_rows_invalid! > 0 || payload.provider_rows_duplicate! > 0 ? "WARN" : "PASS", detail: !hasPayload || !providerAccountingAvailable ? "Provider row accounting metadata is not available." : `Received ${payload.provider_rows_received}; invalid ${payload.provider_rows_invalid}; duplicate ${payload.provider_rows_duplicate}; normalized ${payload.normalized_rows_count}.` },
    { label: "Requested-window coverage", state: "UNAVAILABLE", detail: "The provider response does not establish complete coverage of the requested time window." },
    { label: "Chronological ordering", state: hasCandles ? chronological ? "PASS" : "WARN" : "UNAVAILABLE", detail: hasCandles ? chronological ? "Open times are non-decreasing." : "One or more candles are out of chronological order." : "No candle rows are available to inspect." },
    { label: "OHLC and volume bounds", state: hasCandles ? ohlcValid ? "PASS" : "WARN" : "UNAVAILABLE", detail: hasCandles ? ohlcValid ? "OHLCV values are finite and price/volume bounds are consistent." : "One or more candles contain non-finite values or violate OHLC/volume bounds." : "No candle values are available to inspect." },
    { label: "Candle timestamps", state: hasCandles ? timestampsValid ? "PASS" : "WARN" : "UNAVAILABLE", detail: hasCandles ? timestampsValid ? "Candle timestamps are parseable." : "One or more candle timestamps are invalid." : "No candle timestamps are available to inspect." },
    { label: "Observed interval continuity", state: !hasCandles ? "UNAVAILABLE" : interval === undefined ? "WARN" : missingIntervals > 0 ? "WARN" : "PASS", detail: !hasCandles ? "No candle rows are available to assess interval continuity." : interval === undefined ? "The interval is unsupported; continuity cannot be assessed." : missingIntervals > 0 ? `${missingIntervals} expected interval(s) missing across ${gapCount} gap(s) between returned candles. Edge coverage is not inferred.` : "No missing intervals detected between the first and last returned candles. Edge coverage is not inferred." },
  ];

  return (
    <section className="integrity-diagnostics" aria-label="Market integrity diagnostics">
      <div className="integrity-diagnostics-heading">
        <div><span className="eyebrow">EXPERIMENTAL · FEATURE GATED</span><strong>Integrity diagnostics</strong></div>
        <span>{checks.filter((check) => check.state === "PASS").length} / {checks.length} passed</span>
      </div>
      <ul className="integrity-diagnostics-list">
        {checks.map((check) => (
          <li key={check.label}>
            <span className={`integrity-check-state integrity-check-${check.state.toLowerCase()}`}>{check.state}</span>
            <div><strong>{check.label}</strong><p>{check.detail}</p></div>
          </li>
        ))}
      </ul>
      <p className="markets-footnote">These are structural checks on the returned payload only. They do not verify requested-window coverage, exchange authenticity, market correctness, or provider uptime.</p>
    </section>
  );
}
