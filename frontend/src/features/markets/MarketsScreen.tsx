import { useState } from "react";
import { DataStatePanel } from "../../components/DataState";
import { CandleChart } from "./CandleChart";
import { MarketSnapshot } from "./MarketSnapshot";
import { MarketWatchlist } from "./MarketWatchlist";
import { MarketComparison } from "./MarketComparison";
import { MarketDataFreshness } from "./MarketDataFreshness";
import { MarketQualityHistory, type MarketQualityObservation } from "./MarketQualityHistory";
import { IntegrityDiagnostics } from "./IntegrityDiagnostics";
import { cinApi, type ApiResult, type CoinbaseCandlesResponse } from "../../lib/api";
import "./markets.css";

const INTEGRITY_DIAGNOSTICS_ENABLED = false;

type ProductId = "BTC-USD" | "ETH-USD";
type Granularity = "1m" | "5m" | "15m" | "1h" | "6h" | "1d";

function toQualityObservation(productId: ProductId, granularity: Granularity, response: ApiResult<CoinbaseCandlesResponse>, suffix: string): MarketQualityObservation {
  return {
    id: `${Date.now()}-${suffix}-${productId}`,
    productId,
    granularity,
    state: response.state,
    observedAt: response.retrievedAt ?? response.data?.retrieved_at ?? null,
    source: response.source ?? response.data?.source ?? null,
    candleCount: response.data?.data.length ?? null,
    integrity: response.data ? "Contract accepted" : "Not validated",
  };
}

export function MarketsScreen() {
  const [productId, setProductId] = useState<ProductId>("BTC-USD");
  const [granularity, setGranularity] = useState<Granularity>("1h");
  const [result, setResult] = useState<ApiResult<CoinbaseCandlesResponse> | null>(null);
  const [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState<{ primary: ApiResult<CoinbaseCandlesResponse>; secondary: ApiResult<CoinbaseCandlesResponse> } | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [qualityHistory, setQualityHistory] = useState<MarketQualityObservation[]>([]);
  const requestsBusy = loading || comparisonLoading;

  async function loadCandles() {
    setLoading(true);
    const end = Math.floor(Date.now() / 1000);
    const start = end - 24 * 60 * 60;
    const response = await cinApi.getCoinbaseCandles(productId, granularity, start, end);
    setResult(response);
    setQualityHistory((current) => [toQualityObservation(productId, granularity, response, "single"), ...current].slice(0, 12));
    setLoading(false);
  }

  async function loadComparison() {
    setComparisonLoading(true);
    const end = Math.floor(Date.now() / 1000);
    const start = end - 24 * 60 * 60;
    const otherProduct: ProductId = productId === "BTC-USD" ? "ETH-USD" : "BTC-USD";
    const [primary, secondary] = await Promise.all([
      cinApi.getCoinbaseCandles(productId, granularity, start, end),
      cinApi.getCoinbaseCandles(otherProduct, granularity, start, end),
    ]);
    setComparison({ primary, secondary });
    setQualityHistory((current) => [
      toQualityObservation(otherProduct, granularity, secondary, "comparison-secondary"),
      toQualityObservation(productId, granularity, primary, "comparison-primary"),
      ...current,
    ].slice(0, 12));
    setComparisonLoading(false);
  }

  const candles = result?.data?.data ?? [];
  const displayCandles = [...candles].slice(-12).reverse();

  return (
    <section className="markets-screen" aria-labelledby="markets-title">
      <div className="section-heading">
        <div><span className="eyebrow">PUBLIC MARKET DATA</span><h2 id="markets-title">Markets workspace</h2></div>
        <span className="read-only">READ ONLY</span>
      </div>
      <p className="markets-intro">Coinbase Exchange public USD candles. Requests are read-only and are made only when you select Load candles.</p>
      <MarketWatchlist disabled={requestsBusy} selectedProduct={productId} onSelect={(product) => { setProductId(product); setResult(null); setComparison(null); }} />
      <div className="markets-controls">
        <label>Market
          <select aria-label="Market" disabled={requestsBusy} value={productId} onChange={(event) => { setProductId(event.target.value as ProductId); setResult(null); setComparison(null); }}>
            <option value="BTC-USD">BTC / USD</option><option value="ETH-USD">ETH / USD</option>
          </select>
        </label>
        <label>Interval
          <select aria-label="Interval" disabled={requestsBusy} value={granularity} onChange={(event) => { setGranularity(event.target.value as Granularity); setResult(null); setComparison(null); }}>
            <option value="1m">1 minute</option><option value="5m">5 minutes</option><option value="15m">15 minutes</option>
            <option value="1h">1 hour</option><option value="6h">6 hours</option><option value="1d">1 day</option>
          </select>
        </label>
        <button type="button" onClick={loadCandles} disabled={requestsBusy}>{loading ? "Loading…" : "Load candles"}</button>
      </div>
      <div className="markets-comparison-action"><div><strong>Compare both supported markets</strong><span>Fetch BTC-USD and ETH-USD for one shared 24-hour UTC window at the selected interval.</span></div><button type="button" onClick={loadComparison} disabled={requestsBusy}>{comparisonLoading ? "Comparing…" : "Load comparison"}</button></div>
      {comparison && <div className="panel markets-result">
        <div className="markets-comparison-state"><DataStatePanel state={comparison.primary.state} message={comparison.primary.message} source={comparison.primary.source} retrievedAt={comparison.primary.retrievedAt} /><DataStatePanel state={comparison.secondary.state} message={comparison.secondary.message} source={comparison.secondary.source} retrievedAt={comparison.secondary.retrievedAt} /></div>
        {comparison.primary.data && comparison.secondary.data && <MarketComparison primaryProduct={comparison.primary.data.product_id} primaryCandles={comparison.primary.data.data} secondaryProduct={comparison.secondary.data.product_id} secondaryCandles={comparison.secondary.data.data} />}
      </div>}
      {!result && <div className="markets-empty"><strong>No market request made</strong><p>Select a market and interval, then load public candles to retrieve verified API data.</p></div>}
      {result && <div className="panel markets-result">
        <DataStatePanel state={result.state} message={result.message} source={result.source} retrievedAt={result.retrievedAt} />
        <MarketDataFreshness result={result} />
        {INTEGRITY_DIAGNOSTICS_ENABLED && <IntegrityDiagnostics result={result} />}
        {result.data && <>
          <div className="markets-meta"><span>{result.data.product_id} · {result.data.granularity}</span><span>{result.data.count} candles returned</span></div>
          {result.data.stale_data_warning && <p className="markets-warning">{result.data.stale_data_warning}</p>}
          <MarketSnapshot candles={candles} productId={result.data.product_id} />
          <CandleChart candles={candles} productId={result.data.product_id} />
          <div className="markets-table-wrap"><table className="markets-table">
            <thead><tr><th>Open time (UTC)</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th></tr></thead>
            <tbody>{displayCandles.map((candle) => <tr key={candle.open_time}>
              <td>{candle.open_time_utc}</td><td>{candle.open}</td><td>{candle.high}</td><td>{candle.low}</td><td>{candle.close}</td><td>{candle.volume}</td>
            </tr>)}</tbody>
          </table></div>
          <p className="markets-footnote">Showing the latest {displayCandles.length} returned rows. Values are provider-reported candle fields, not a trading interface.</p>
        </>}
      </div>}
      <MarketQualityHistory observations={qualityHistory} />
      <p className="footer-note">Research and monitoring only. No order placement, trade execution, wallet access, private keys or fund movement.</p>
    </section>
  );
}
