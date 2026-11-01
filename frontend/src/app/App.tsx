import { useEffect, useState } from "react";
import { cinApi, type ApiResult } from "../lib/api";
import { marketsFeatureEnabled } from "../lib/featureFlags";
import { MarketsScreen } from "../features/markets/MarketsScreen";
import { OverviewTerminal } from "../features/overview/OverviewTerminal";

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
          <OverviewTerminal health={health} readiness={readiness} />
        ) : (
          <section className="panel page-placeholder"><span className="eyebrow">MODULE STATUS</span><h2>{active} integration pending</h2><p>This module is not connected to a verified API contract. No sample values are presented as live information.</p><span className="state-pill neutral">NOT IMPLEMENTED</span></section>
        )}
      </main>
    </div>
  );
}

export default App;
