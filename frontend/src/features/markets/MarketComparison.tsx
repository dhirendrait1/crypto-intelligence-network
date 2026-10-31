import type { CoinbaseCandle } from "../../lib/api";

interface MarketComparisonProps {
  primaryProduct: string;
  primaryCandles: CoinbaseCandle[];
  secondaryProduct: string;
  secondaryCandles: CoinbaseCandle[];
}

function sharedPerformance(primaryCandles: CoinbaseCandle[], secondaryCandles: CoinbaseCandle[]) {
  const primaryByTime = new Map(primaryCandles.map((candle) => [candle.open_time, candle]));
  const secondaryByTime = new Map(secondaryCandles.map((candle) => [candle.open_time, candle]));
  const sharedTimes = [...primaryByTime.keys()]
    .filter((time) => secondaryByTime.has(time))
    .sort((a, b) => a - b);

  if (sharedTimes.length === 0) return { primary: null, secondary: null, sharedCount: 0 };
  const firstTime = sharedTimes[0];
  const lastTime = sharedTimes[sharedTimes.length - 1];
  const primaryStart = primaryByTime.get(firstTime)!.open;
  const secondaryStart = secondaryByTime.get(firstTime)!.open;
  if (primaryStart === 0 || secondaryStart === 0) {
    return { primary: null, secondary: null, sharedCount: sharedTimes.length };
  }
  const primaryEnd = primaryByTime.get(lastTime)!.close;
  const secondaryEnd = secondaryByTime.get(lastTime)!.close;
  return {
    primary: ((primaryEnd - primaryStart) / primaryStart) * 100,
    secondary: ((secondaryEnd - secondaryStart) / secondaryStart) * 100,
    sharedCount: sharedTimes.length,
  };
}

function format(value: number | null): string {
  return value === null ? "Unavailable" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function MarketComparison({ primaryProduct, primaryCandles, secondaryProduct, secondaryCandles }: MarketComparisonProps) {
  const { primary, secondary, sharedCount } = sharedPerformance(primaryCandles, secondaryCandles);
  const comparable = primary !== null && secondary !== null;
  const difference = comparable ? primary - secondary : null;

  return (
    <section className="market-comparison" aria-label="Relative market performance comparison">
      <div className="market-comparison-heading"><div><span className="eyebrow">RELATIVE PERFORMANCE</span><strong>{primaryProduct} vs {secondaryProduct}</strong></div><span>{sharedCount} shared candle timestamps</span></div>
      <div className="market-comparison-grid">
        <article className="comparison-metric"><span>{primaryProduct}</span><strong className={primary === null ? "" : primary >= 0 ? "snapshot-positive" : "snapshot-negative"}>{format(primary)}</strong><small>First shared candle open to last shared candle close</small></article>
        <article className="comparison-metric"><span>{secondaryProduct}</span><strong className={secondary === null ? "" : secondary >= 0 ? "snapshot-positive" : "snapshot-negative"}>{format(secondary)}</strong><small>First shared candle open to last shared candle close</small></article>
        <article className="comparison-metric"><span>Relative difference</span><strong>{difference === null ? "Unavailable" : format(difference)}</strong><small>{difference === null ? "Both markets need shared timestamps and valid non-zero baselines" : difference > 0 ? `${primaryProduct} outperformed` : difference < 0 ? `${secondaryProduct} outperformed` : "Equal percentage performance"}</small></article>
      </div>
      <p className="markets-footnote">Returns use only matching candle open timestamps from both returned series, reducing misleading comparisons when provider responses contain different candle windows. This is historical percentage performance, not a forecast, recommendation, or trading signal.</p>
    </section>
  );
}
