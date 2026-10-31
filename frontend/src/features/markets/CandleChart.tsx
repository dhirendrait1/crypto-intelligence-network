import type { CoinbaseCandle } from "../../lib/api";

interface CandleChartProps {
  candles: CoinbaseCandle[];
  productId: string;
}

const WIDTH = 800;
const HEIGHT = 360;
const PLOT_TOP = 22;
const PLOT_BOTTOM = 238;
const VOLUME_TOP = 270;
const VOLUME_BOTTOM = 326;

function formatPrice(value: number): string {
  return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export function CandleChart({ candles, productId }: CandleChartProps) {
  if (candles.length === 0) {
    return <div className="candle-chart-empty" role="status">No candle observations are available to chart.</div>;
  }

  const ordered = [...candles].sort((a, b) => a.open_time - b.open_time);
  const low = Math.min(...ordered.map((candle) => candle.low));
  const high = Math.max(...ordered.map((candle) => candle.high));
  const priceRange = high - low || Math.max(Math.abs(high) * 0.002, 1);
  const minPrice = low - priceRange * 0.06;
  const maxPrice = high + priceRange * 0.06;
  const maxVolume = Math.max(...ordered.map((candle) => candle.volume), 1);
  const plotHeight = PLOT_BOTTOM - PLOT_TOP;
  const step = WIDTH / ordered.length;
  const bodyWidth = Math.max(2, Math.min(13, step * 0.62));
  const y = (price: number) => PLOT_BOTTOM - ((price - minPrice) / (maxPrice - minPrice)) * plotHeight;
  const chartLabel = `${productId} candlestick chart, ${ordered.length} candles, price range ${formatPrice(low)} to ${formatPrice(high)} USD`;

  return (
    <section className="candle-chart" aria-label="Market price chart">
      <div className="candle-chart-heading">
        <div><span className="eyebrow">PRICE ACTION</span><strong>{productId} · USD</strong></div>
        <span>{ordered.length} candles</span>
      </div>
      <div className="candle-chart-scroll">
        <svg className="candle-chart-svg" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={chartLabel}>
          {[0, 1, 2, 3].map((tick) => {
            const value = maxPrice - ((maxPrice - minPrice) * tick) / 3;
            const tickY = y(value);
            return <g key={tick}>
              <line x1="0" x2={WIDTH} y1={tickY} y2={tickY} className="chart-grid-line" />
              <text x={WIDTH - 4} y={tickY - 5} textAnchor="end" className="chart-axis-label">{formatPrice(value)}</text>
            </g>;
          })}
          {ordered.map((candle, index) => {
            const center = step * index + step / 2;
            const rising = candle.close >= candle.open;
            const top = y(Math.max(candle.open, candle.close));
            const bottom = y(Math.min(candle.open, candle.close));
            const bodyHeight = Math.max(2, bottom - top);
            const volumeHeight = (candle.volume / maxVolume) * (VOLUME_BOTTOM - VOLUME_TOP);
            return <g key={candle.open_time} data-candle-open-time={candle.open_time} className={rising ? "candle-rising" : "candle-falling"}>
              <line x1={center} x2={center} y1={y(candle.high)} y2={y(candle.low)} className="candle-wick" />
              <rect x={center - bodyWidth / 2} y={top} width={bodyWidth} height={bodyHeight} className="candle-body" rx="1" />
              <rect x={center - bodyWidth / 2} y={VOLUME_BOTTOM - volumeHeight} width={bodyWidth} height={Math.max(1, volumeHeight)} className="volume-bar" />
            </g>;
          })}
          <line x1="0" x2={WIDTH} y1={VOLUME_TOP - 7} y2={VOLUME_TOP - 7} className="chart-divider-line" />
          <text x="4" y={VOLUME_TOP - 12} className="chart-axis-label">VOLUME</text>
          <text x="4" y={HEIGHT - 8} className="chart-axis-label">{new Date(ordered[0].open_time * 1000).toISOString().slice(0, 16).replace("T", " ")}</text>
          <text x={WIDTH - 4} y={HEIGHT - 8} textAnchor="end" className="chart-axis-label">{new Date(ordered[ordered.length - 1].open_time * 1000).toISOString().slice(0, 16).replace("T", " ")}</text>
        </svg>
      </div>
      <div className="candle-chart-legend"><span><i className="legend-up" /> Close at or above open</span><span><i className="legend-down" /> Close below open</span><span>Volume · provider reported</span></div>
      <p className="markets-footnote">Chart uses returned OHLCV observations only. It does not estimate missing prices or generate trading signals.</p>
    </section>
  );
}
