import { useState } from "react";
import { NeuralField } from "../../components/NeuralField";
import { DataStatePanel } from "../../components/DataState";
import { cinApi, type ApiResult } from "../../lib/api";
import "./overview.css";

type Props = {
  health: ApiResult<Record<string, unknown>> | null;
  readiness: ApiResult<Record<string, unknown>> | null;
};

const integrity = [
  ["Market identity", "NOT CHECKED"],
  ["Candle chronology", "NOT CHECKED"],
  ["Gap detection", "NOT CHECKED"],
  ["Source freshness", "UNKNOWN"],
];
const streams = [
  ["MARKET DATA", "Awaiting verified candles", "01"],
  ["TECHNICAL ANALYSIS", "No validated assessment", "02"],
  ["COIN SCREENING", "No accepted shortlist", "03"],
  ["NEWS + SENTIMENT", "No verified feed", "04"],
  ["ALERT INTELLIGENCE", "Monitoring inactive", "05"],
];
const sources = ["Coinbase public data", "Kraken fallback", "GDELT / public RSS", "Assessment evidence"];

export function OverviewTerminal({ health, readiness }: Props) {
  const [motionEnabled, setMotionEnabled] = useState(true);

  return (
    <>
      <section className="notice" role="status">
        <span className="notice-icon" aria-hidden="true">i</span>
        <div><strong>Preview interface — demo mode</strong><p>These overview cards are layout fixtures, not live market data. Markets requests are separately gated and user-initiated.</p></div>
        <span className="demo-tag">DESIGN PREVIEW</span>
      </section>
      <div className="cin-terminal">
        <div className="cin-command-bar">
          <div className="cin-command-brand"><span className="cin-io-dot" />CIN // NEURAL INTELLIGENCE COMMAND CENTER</div>
          <div className="cin-command-right"><span>PUBLIC DATA · RESEARCH</span><span className="cin-tiny-tag">READ ONLY</span></div>
        </div>

        <section className="cin-tile-row" aria-label="Market status overview">
          <article className="cin-terminal-card cin-summary">
            <div className="cin-kicker">BTC / USD <span>COINBASE PUBLIC</span></div>
            <div className="cin-big-value">— <small>USD</small></div>
            <div className="cin-muted">Price unverified · no feed loaded</div>
            <div className="cin-card-bottom"><span>PRICE · UNKNOWN</span><span className="cin-amber">● OFFLINE VIEW</span></div>
          </article>
          <article className="cin-terminal-card cin-summary">
            <div className="cin-kicker">ETH / USD <span>COINBASE PUBLIC</span></div>
            <div className="cin-big-value">— <small>USD</small></div>
            <div className="cin-muted">Price unverified · no feed loaded</div>
            <div className="cin-card-bottom"><span>CHANGE · UNKNOWN</span><span className="cin-amber">● OFFLINE VIEW</span></div>
          </article>
          <article className="cin-terminal-card cin-summary">
            <div className="cin-kicker">PROVIDER INTEGRITY <span>GATED</span></div>
            <div className="cin-big-value">— <small>STATUS</small></div>
            <div className="cin-muted">No provider observation accepted</div>
            <div className="cin-card-bottom"><span>FRESHNESS · UNKNOWN</span><span>NO TIMESTAMP</span></div>
          </article>
          <article className="cin-terminal-card cin-summary">
            <div className="cin-kicker">INTELLIGENCE ALERTS <span>READ ONLY</span></div>
            <div className="cin-big-value">— <small>ALERTS</small></div>
            <div className="cin-muted">Alert integration not connected</div>
            <div className="cin-card-bottom"><span>DELIVERY · UNKNOWN</span><span>NOT ACTIVE</span></div>
          </article>
        </section>

        <div className="cin-top-grid">
          <section className="cin-terminal-card cin-mini-panel" aria-label="Market structure layout preview">
            <div className="cin-panel-heading"><div><span className="cin-kicker">01 / PRICE INTELLIGENCE</span><h2>Market structure</h2></div><span className="cin-outline">NO CANDLES</span></div>
            <div className="cin-trace-frame" aria-hidden="true"><div className="cin-trace-grid" /><div className="cin-illustration-watermark">VISUAL MOTIF · NO MARKET DATA</div></div>
            <div className="cin-panel-foot"><span>BTC · ETH · USD QUOTE</span><span>MANUAL LOAD IN MARKETS</span></div>
          </section>
          <section className="cin-terminal-card cin-mini-panel" aria-label="Integrity audit status">
            <div className="cin-panel-heading"><div><span className="cin-kicker">02 / PROVIDER VALIDATION</span><h2>Integrity inspector</h2></div><span className="cin-outline">NOT RUN</span></div>
            <div className="cin-integrity-list">
              {integrity.map(([name, status]) => <div key={name}><span>{name}</span><strong>{status}</strong></div>)}
            </div>
            <div className="cin-panel-foot"><span>FAIL CLOSED ON UNKNOWN</span><span>PROVENANCE REQUIRED</span></div>
          </section>
        </div>

        <section className="cin-terminal-card cin-neural-panel" aria-label="Intelligence network visualization">
          <div className="cin-panel-heading cin-network-heading"><div><span className="cin-kicker">03 / MULTI-SOURCE INTELLIGENCE LAYER</span><h2>Neural intelligence network</h2></div><button className="cin-motion-button" type="button" aria-pressed={!motionEnabled} onClick={() => setMotionEnabled(value => !value)}>{motionEnabled ? "Pause motion" : "Resume motion"}</button></div>
          <div className="cin-neural-grid">
            <div className="cin-channel-col">
              {streams.slice(0, 3).map(([name, state, num]) => <div className="cin-channel" key={num}><span className="cin-channel-num">{num}</span><div><strong>{name}</strong><small>{state}</small></div><span className="cin-channel-dot" aria-hidden="true" /></div>)}
            </div>
            <div className="cin-neural-stage">
              <div className="cin-field-crosshair" aria-hidden="true" />
              <NeuralField paused={!motionEnabled} />
              <div className="cin-stage-label cin-stage-label-top">TOPOLOGY RENDER / VISUALIZATION ONLY</div>
              <div className="cin-stage-label cin-stage-label-bottom">NO LIVE INPUT · NO MODEL OUTPUT</div>
            </div>
            <div className="cin-channel-col">
              {streams.slice(3).map(([name, state, num]) => <div className="cin-channel" key={num}><span className="cin-channel-num">{num}</span><div><strong>{name}</strong><small>{state}</small></div><span className="cin-channel-dot" aria-hidden="true" /></div>)}
              <div className="cin-channel"><span className="cin-channel-num">06</span><div><strong>SOURCE RELIABILITY</strong><small>Evidence not loaded</small></div><span className="cin-channel-dot" aria-hidden="true" /></div>
            </div>
          </div>
          <div className="cin-network-legend"><span><i className="cin-legend-cyan" />Conceptual analysis nodes</span><span><i className="cin-legend-gold" />Conceptual source links</span><span>3D topology is decorative, not measured relationships</span></div>
        </section>

        <div className="cin-bottom-grid">
          <section className="cin-terminal-card cin-ledger">
            <div className="cin-panel-heading"><div><span className="cin-kicker">04 / EVIDENCE + AUDIT</span><h2>Provider provenance ledger</h2></div><span className="cin-outline">UNVERIFIED</span></div>
            <div className="cin-ledger-scroll">
              <table><thead><tr><th>Source</th><th>Observed at</th><th>Freshness</th><th>State</th></tr></thead>
              <tbody>{sources.map(s => <tr key={s}><td>{s}</td><td>—</td><td>UNKNOWN</td><td><span className="cin-ledger-state">NOT LOADED</span></td></tr>)}</tbody></table>
            </div>
          </section>
          <section className="cin-terminal-card cin-ledger">
            <div className="cin-panel-heading"><div><span className="cin-kicker">05 / RESEARCH OBSERVABILITY</span><h2>Signal &amp; assessment timeline</h2></div><span className="cin-outline">EMPTY</span></div>
            <div className="cin-signal-empty"><span className="cin-signal-ring" aria-hidden="true" /><strong>No verified research events</strong><small>Signal curves, confidence, and sentiment appear only after validated source data is connected.</small></div>
          </section>
        </div>
        {cinApi.configured && <section className="cin-system-pair" aria-label="API service checks"><article className="cin-terminal-card"><DataStatePanel state={health?.state ?? "unknown"} message={health?.message ?? "Checking CIN service health…"} /></article><article className="cin-terminal-card"><DataStatePanel state={readiness?.state ?? "unknown"} message={readiness?.message ?? "Checking CIN service readiness…"} /></article></section>}
        <div className="cin-terminal-footer"><span>CIN · CRYPTO INTELLIGENCE NETWORK</span><span>NO TRADING · NO ORDERS · NO WALLETS · NO FUND MOVEMENT</span><span>DESIGN PREVIEW · NO PRODUCTION ACTIVATION</span></div>
      </div>
    </>
  );
}
