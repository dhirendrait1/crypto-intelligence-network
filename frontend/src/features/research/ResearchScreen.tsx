import { classifyCoinbaseResearch } from "./coinbaseResearchContract";
import "./research.css";
/** No fetch or Vite-bundled operator token; props must come from future approved server gateway. */
interface Props { enabled?:boolean; payload?:unknown; httpStatus?:number|null; expectedProductId?:"BTC-USD"|"ETH-USD" }
export function ResearchScreen({enabled=false,payload,httpStatus,expectedProductId}:Props) {
  const view=classifyCoinbaseResearch({enabled,payload,httpStatus,expectedProductId});
  return <section className="cin-research" aria-label="Coinbase research dashboard">
    <div className="notice" role="status"><span className="notice-icon" aria-hidden="true">i</span>
      <div><strong>Coinbase shortlist research · staging schema</strong><p>Display-only contract. No live research API calls or browser-held credentials.</p></div>
      <span className="demo-tag">NOT LIVE</span></div>
    <div className="cin-research-grid">
      <article className="cin-terminal-card cin-research-card">
        <div className="cin-panel-heading"><div><span className="cin-kicker">01 / MARKET RESEARCH</span><h2>Eligibility assessment</h2></div><span className="cin-outline" role="status">{view.label}</span></div>
        <p className="cin-research-message">{view.message}</p>
        <dl className="cin-research-details">
          <div><dt>Product</dt><dd>{view.productId??"—"}</dd></div>
          <div><dt>Market status</dt><dd>{view.marketStatus}</dd></div>
          <div><dt>Shortlist</dt><dd>NOT APPROVED</dd></div>
        </dl>
      </article>
      <article className="cin-terminal-card cin-research-card">
        <div className="cin-panel-heading"><div><span className="cin-kicker">02 / EVIDENCE CONTROLS</span><h2>Verification gates</h2></div><span className="cin-outline">FAIL CLOSED</span></div>
        <dl className="cin-research-details">
          <div><dt>Data integrity</dt><dd>{view.evidence.data}</dd></div>
          <div><dt>Liquidity</dt><dd>{view.evidence.liquidity}</dd></div>
          <div><dt>Security</dt><dd>{view.evidence.security}</dd></div>
          <div><dt>Risk</dt><dd>{view.evidence.risk}</dd></div>
        </dl>
        <p className="cin-research-provenance">{view.provenance}</p>
      </article>
    </div>
    <p className="cin-research-footnote">Read-only · no fabricated price, volume or scoring · no orders, wallets or fund movement.</p>
  </section>;
}
