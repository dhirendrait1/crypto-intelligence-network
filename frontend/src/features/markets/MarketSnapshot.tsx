import type { CoinbaseCandle } from "../../lib/api";

interface MarketSnapshotProps {
  candles: CoinbaseCandle[];
  productId: string;
}

function money(value: number): string {
  return value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
}

function quantity(value: number): string {
  return value.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

export function MarketSnapshot({ candles, productId }: MarketSnapshotProps) {
  if (candles.length === 0) {
    return <section className="market-snapshot-empty" aria-label="Market snapshot">Snapshot unavailable until verified candle data is loaded.</section>;
  }

  const ordered = [...candles].sort((a, b) => a.open_time - b.open_time);
  const first = ordered[0];
  const latest = ordered[ordered.length - 1];
  const high = Math.max(...ordered.map((candle) => candle.high));
  const low = Math.min(...ordered.map((candle) => candle.low));
  const totalVolume = ordered.reduce((sum, candle) => sum + candle.volume, 0);
  const change = latest.close - first.open;
  const changePercent = first.open === 0 ? null : (change / first.open) * 100;
  const positive = change >= 0;

  const metrics = [
    { label: "Latest close", value: money(latest.close), detail: "Last returned candle close" },
    { label: "Period change", value: `${positive ? "+" : ""}${money(change)}`, detail: changePercent === null ? "Percentage unavailable (zero baseline)" : `${positive ? "+" : ""}${changePercent.toFixed(2)}% from first open`, tone: positive ? "positive" : "negative" },
    { label: "Period high", value: money(high), detail: "Highest returned candle high" },
    { label: "Period low", value: money(low), detail: "Lowest returned candle low" },
    { label: "Reported volume", value: quantity(totalVolume), detail: "Sum of returned candle volumes" },
  ];

  return (
    <section className="market-snapshot" aria-label={`${productId} market snapshot`}>
      <div className="market-snapshot-heading"><div><span className="eyebrow">MARKET SNAPSHOT</span><strong>{productId}</strong></div><span>{ordered.length} observations</span></div>
      <div className="market-snapshot-grid">
        {metrics.map((metric) => <article className="snapshot-metric" key={metric.label}>
          <span>{metric.label}</span>
          <strong className={metric.tone ? `snapshot-${metric.tone}` : undefined}>{metric.value}</strong>
          <small>{metric.detail}</small>
        </article>)}
      </div>
      <p className="markets-footnote">Derived only from the currently returned candle window. Volume units follow the exchange response; this is not a live quote or trading signal.</p>
    </section>
  );
}
