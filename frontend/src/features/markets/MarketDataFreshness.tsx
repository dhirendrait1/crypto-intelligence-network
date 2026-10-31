import type { ApiResult, CoinbaseCandlesResponse } from "../../lib/api";

interface MarketDataFreshnessProps {
  result: ApiResult<CoinbaseCandlesResponse>;
}

function formatAge(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return "Unavailable";
  if (seconds < 60) return `${Math.floor(seconds)} sec`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} hr`;
}

export function MarketDataFreshness({ result }: MarketDataFreshnessProps) {
  const data = result.data;
  const age = data?.latest_closed_candle_age_seconds ?? null;
  const threshold = data?.stale_threshold_seconds;
  const isBeyondThreshold = age !== null && typeof threshold === "number" && age > threshold;
  const status = result.state === "stale" || isBeyondThreshold ? "STALE" : result.state === "fresh" ? "FRESH" : result.state.toUpperCase();

  return (
    <section className="market-freshness" aria-label="Market data freshness and integrity">
      <div className="market-freshness-heading"><div><span className="eyebrow">DATA QUALITY</span><strong>Freshness & integrity</strong></div><span className={status === "FRESH" ? "freshness-status freshness-good" : "freshness-status freshness-caution"} role="status">{status}</span></div>
      <div className="market-freshness-grid">
        <article><span>Latest closed candle age</span><strong>{formatAge(age)}</strong></article>
        <article><span>Backend stale threshold</span><strong>{typeof threshold === "number" ? formatAge(threshold) : "Unavailable"}</strong></article>
        <article><span>Latest closed candle (UTC)</span><strong>{data?.latest_closed_candle_close_time_utc ?? "Unavailable"}</strong></article>
        <article><span>API retrieval time (UTC)</span><strong>{data?.retrieved_at ?? result.retrievedAt ?? "Unavailable"}</strong></article>
        <article><span>Returned / declared count</span><strong>{data ? `${data.data.length} / ${data.count}` : "Unavailable"}</strong></article>
        <article><span>Source endpoint</span><strong>{data?.source_endpoint ?? result.source ?? "Unavailable"}</strong></article>
      </div>
      {data?.stale_data_warning && <p className="freshness-warning">{data.stale_data_warning}</p>}
      {!data && <p className="markets-footnote">No validated candle payload is available. Freshness cannot be established.</p>}
      <p className="markets-footnote">Status follows the API freshness classification and its reported threshold. This panel does not infer missing observations or claim provider uptime.</p>
    </section>
  );
}
