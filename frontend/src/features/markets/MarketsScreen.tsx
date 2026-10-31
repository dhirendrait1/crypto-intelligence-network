import { useState } from "react";
import { DataStatePanel } from "../../components/DataState";
import { CandleChart } from "./CandleChart";
import { MarketSnapshot } from "./MarketSnapshot";
import { cinApi, type ApiResult, type CoinbaseCandlesResponse } from "../../lib/api";
import "./markets.css";

type ProductId = "BTC-USD" | "ETH-USD";
type Granularity = "1m" | "5m" | "15m" | "1h" | "6h" | "1d";

export function MarketsScreen() {
  const [productId, setProductId] = useState<ProductId>("BTC-USD");
  const [granularity, setGranularity] = useState<Granularity>("1h");
  const [result, setResult] = useState<ApiResult<CoinbaseCandlesResponse> | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadCandles() {
    setLoading(true);
    const end = Math.floor(Date.now() / 1000);
    const start = end - 24 * 60 * 60;
    const response = await cinApi.getCoinbaseCandles(productId, granularity, start, end);
    setResult(response);
    setLoading(false);
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
      <div className="markets-controls">
        <label>Market
          <select aria-label="Market" value={productId} onChange={(event) => { setProductId(event.target.value as ProductId); setResult(null); }}>
            <option value="BTC-USD">BTC / USD</option><option value="ETH-USD">ETH / USD</option>
          </select>
        </label>
        <label>Interval
          <select aria-label="Interval" value={granularity} onChange={(event) => { setGranularity(event.target.value as Granularity); setResult(null); }}>
            <option value="1m">1 minute</option><option value="5m">5 minutes</option><option value="15m">15 minutes</option>
            <option value="1h">1 hour</option><option value="6h">6 hours</option><option value="1d">1 day</option>
          </select>
        </label>
        <button type="button" onClick={loadCandles} disabled={loading}>{loading ? "Loading…" : "Load candles"}</button>
      </div>
      {!result && <div className="markets-empty"><strong>No market request made</strong><p>Select a market and interval, then load public candles to retrieve verified API data.</p></div>}
      {result && <div className="panel markets-result">
        <DataStatePanel state={result.state} message={result.message} source={result.source} retrievedAt={result.retrievedAt} />
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
      <p className="footer-note">Research and monitoring only. No order placement, trade execution, wallet access, private keys or fund movement.</p>
    </section>
  );
}
