export interface MarketQualityObservation {
  id: string;
  productId: string;
  granularity: string;
  state: string;
  observedAt: string | null;
  source: string | null;
  candleCount: number | null;
  integrity: "Contract accepted" | "Not validated";
}

interface MarketQualityHistoryProps {
  observations: MarketQualityObservation[];
}

export function MarketQualityHistory({ observations }: MarketQualityHistoryProps) {
  return (
    <section className="market-quality-history" aria-label="Market data quality history">
      <div className="market-quality-history-heading">
        <div><span className="eyebrow">SESSION OBSERVATIONS</span><strong>Data quality history</strong></div>
        <span>{observations.length} / 12</span>
      </div>
      {observations.length === 0 ? (
        <p className="markets-footnote">No observations recorded in this screen session. Load candles or a comparison to begin a history.</p>
      ) : (
        <div className="market-quality-table-wrap">
          <table className="market-quality-table">
            <thead><tr><th>Market</th><th>Interval</th><th>API state</th><th>Integrity</th><th>Candles</th><th>Source</th><th>Observed at (UTC)</th></tr></thead>
            <tbody>{observations.map((item) => (
              <tr key={item.id}>
                <td>{item.productId}</td><td>{item.granularity}</td><td><span className={item.state === "fresh" ? "quality-state quality-fresh" : "quality-state"}>{item.state.toUpperCase()}</span></td>
                <td>{item.integrity}</td><td>{item.candleCount ?? "—"}</td><td>{item.source ?? "Unavailable"}</td><td>{item.observedAt ?? "Unavailable"}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <p className="markets-footnote">Session-only history, newest first, capped at 12 manual API observations. It is cleared when this screen session ends; it is not persisted or an uptime statistic.</p>
    </section>
  );
}
