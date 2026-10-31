import { useEffect, useState } from "react";
import { cinApi, type ApiResult } from "../lib/api";
import { marketsFeatureEnabled } from "../lib/featureFlags";
import { MarketsScreen } from "../features/markets/MarketsScreen";
import { DataStatePanel } from "../components/DataState";

const sections = ["Overview", "Markets", "Screening", "Analysis", "Research", "News", "Alerts", "System Health"] as const;
type Section = typeof sections[number];

function App() {
  const [active, setActive] = useState<Section>("Overview");
  const [health, setHealth] = useState<ApiResult<Record<string, unknown>> | null>(null);
  const [readiness, setReadiness] = useState<ApiResult<Record<string, unknown>> | null>(null);

  useEffect(() => {
    if (!cinApi.configured) return;
    let mounted = true;
    Promise.all([cinApi.getHealth(), cinApi.getReadiness()]).then(([healthResult, readyResult]) => {
      if (mounted) { setHealth(healthResult); setReadiness(readyResult); }
    });
    return () => { mounted = false; };
  }, []);

  const visibleSections = sections.filter((section) => section !== "Markets" || marketsFeatureEnabled);

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand"><span className="brand-mark">C</span><span><strong>CIN</strong><small>CRYPTO INTELLIGENCE NETWORK</small></span></div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {visibleSections.map((section) => (
            <button key={section} className={active === section ? "nav-item active" : "nav-item"} onClick={() => setActive(section)} aria-current={active === section ? "page" : undefined}>
              <span className="nav-dot" aria-hidden="true" />{section}
              {["Alerts", "Research", "News"].includes(section) && <span className="planned">PLANNED</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot"><span className="status-dot" /> {cinApi.configured ? "API health check enabled" : "API base URL not configured"}</div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div><span className="eyebrow">INTELLIGENCE TERMINAL</span><h1>{active}</h1></div>
          <div className="topbar-right"><span className="read-only">READ ONLY</span><span className="avatar">C</span></div>
        </header>

        {active === "Markets" && marketsFeatureEnabled ? <MarketsScreen /> : active === "Overview" ? (
          <>
            <section className="notice" role="status">
              <span className="notice-icon">i</span>
              <div><strong>Preview interface — demo mode</strong><p>These overview cards are layout fixtures, not live market data. Markets requests are separately gated and user-initiated.</p></div>
              <span className="demo-tag">DEMO DATA</span>
            </section>
            <div className="section-heading"><div><span className="eyebrow">MARKET SNAPSHOT</span><h2>Market intelligence overview</h2></div><span className="timestamp">Fixture snapshot · no live feed</span></div>
            <div className="metric-grid">
              <article className="metric-card"><span>BTC / USD</span><strong>—</strong><small>Live feed not connected</small></article>
              <article className="metric-card"><span>ETH / USD</span><strong>—</strong><small>Live feed not connected</small></article>
              <article className="metric-card"><span>DATA SOURCES</span><strong>0 <em>/ 0</em></strong><small>Provider health unavailable</small></article>
              <article className="metric-card"><span>ACTIVE ALERTS</span><strong>—</strong><small>Alert service not implemented</small></article>
            </div>
            {cinApi.configured && <div className="content-grid"><article className="panel"><DataStatePanel state={health?.state ?? "unknown"} message={health?.message ?? "Checking CIN service health…"} /></article><article className="panel"><DataStatePanel state={readiness?.state ?? "unknown"} message={readiness?.message ?? "Checking CIN service readiness…"} /></article></div>}
            <div className="content-grid">
              <article className="panel"><div className="panel-head"><div><span className="eyebrow">SYSTEM STATUS</span><h3>Data availability</h3></div><span className="state-pill neutral">NOT CONNECTED</span></div><div className="empty-state"><span className="empty-symbol">⌁</span><strong>Waiting for verified API connection</strong><p>Provider status, freshness and coverage will appear here after contract validation.</p></div></article>
              <article className="panel"><div className="panel-head"><div><span className="eyebrow">RESEARCH FEED</span><h3>Latest intelligence</h3></div><span className="state-pill neutral">NOT AVAILABLE</span></div><div className="empty-state"><span className="empty-symbol">◷</span><strong>No assessments loaded</strong><p>Assessment history is not connected in this preview.</p></div></article>
            </div>
            <div className="footer-note">CIN provides research and monitoring only. No trading, order execution, wallet control or fund movement.</div>
          </>
        ) : (
          <section className="panel page-placeholder"><span className="eyebrow">MODULE STATUS</span><h2>{active} integration pending</h2><p>This module is not connected to a verified API contract. No sample values are presented as live information.</p><span className="state-pill neutral">NOT IMPLEMENTED</span></section>
        )}
      </main>
    </div>
  );
}

export default App;
