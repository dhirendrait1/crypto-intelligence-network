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
  const chronological = candles.every((candle, index) => index === 0 || candle.open_time >= candles[index - 1].open_time);
  const ohlcValid = candles.every((candle) =>
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

  const checks: Diagnostic[] = [
    { label: "Response contract", state: hasPayload ? "PASS" : "UNAVAILABLE", detail: hasPayload ? "The frontend API contract accepted this payload." : "No validated candle payload is available." },
    { label: "Declared candle count", state: hasPayload ? countMatches ? "PASS" : "WARN" : "UNAVAILABLE", detail: hasPayload ? `${candles.length} returned / ${payload.count} declared` : "Cannot compare counts without a payload." },
    { label: "Chronological ordering", state: hasPayload ? chronological ? "PASS" : "WARN" : "UNAVAILABLE", detail: hasPayload ? chronological ? "Open times are non-decreasing." : "One or more candles are out of chronological order." : "No candle sequence to inspect." },
    { label: "OHLC and volume bounds", state: hasPayload ? ohlcValid ? "PASS" : "WARN" : "UNAVAILABLE", detail: hasPayload ? ohlcValid ? "Price bounds and non-negative volume are consistent." : "One or more candles violate OHLC or volume bounds." : "No candle values to inspect." },
    { label: "Candle timestamps", state: hasPayload ? timestampsValid ? "PASS" : "WARN" : "UNAVAILABLE", detail: hasPayload ? timestampsValid ? "Candle timestamps are parseable." : "One or more candle timestamps are invalid." : "No candle timestamps to inspect." },
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
      <p className="markets-footnote">These are structural checks on the returned payload only. They do not verify exchange authenticity, market correctness, completeness outside the response, or provider uptime.</p>
    </section>
  );
}
