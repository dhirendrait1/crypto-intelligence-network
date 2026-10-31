import type { CoinbaseCandle } from "../../lib/api";

interface MarketComparisonProps {
  primaryProduct: string;
  primaryCandles: CoinbaseCandle[];
  secondaryProduct: string;
  secondaryCandles: CoinbaseCandle[];
}

function performance(candles: CoinbaseCandle[]): number | null {
  if (candles.length === 0) return null;
  const ordered = [...candles].sort((a, b) => a.open_time - b.open_time);
  const baseline = ordered[0].open;
  if (baseline === 0) return null;
  return ((ordered[ordered.length - 1].close - baseline) / baseline) * 100;
}

function format(value: number | null): string {
  return value === null ? "Unavailable" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function MarketComparison({ primaryProduct, primaryCandles, secondaryProduct, secondaryCandles }: MarketComparisonProps) {
  const primary = performance(primaryCandles);
  const secondary = performance(secondaryCandles);
  const comparable = primary !== null && secondary !== null;
  const difference = comparable ? primary - secondary : null;

  return (
    <section className="market-comparison" aria-label="Relative market performance comparison">
      <div className="market-comparison-heading"><div><span className="eyebrow">RELATIVE PERFORMANCE</span><strong>{primaryProduct} vs {secondaryProduct}</strong></div><span>Same requested window</span></div>
      <div className="market-comparison-grid">
        <article className="comparison-metric"><span>{primaryProduct}</span><strong className={primary === null ? "" : primary >= 0 ? "snapshot-positive" : "snapshot-negative"}>{format(primary)}</strong><small>First candle open to last candle close</small></article>
        <article className="comparison-metric"><span>{secondaryProduct}</span><strong className={secondary === null ? "" : secondary >= 0 ? "snapshot-positive" : "snapshot-negative"}>{format(secondary)}</strong><small>First candle open to last candle close</small></article>
        <article className="comparison-metric"><span>Relative difference</span><strong>{difference === null ? "Unavailable" : format(difference)}</strong><small>{difference === null ? "Both markets need valid non-zero baselines" : difference > 0 ? `${primaryProduct} outperformed` : difference < 0 ? `${secondaryProduct} outperformed` : "Equal percentage performance"}</small></article>
      </div>
      <p className="markets-footnote">Comparison uses each market's returned candle series over the same requested UTC window. It is historical percentage performance, not a forecast, recommendation, or trading signal.</p>
    </section>
  );
}
