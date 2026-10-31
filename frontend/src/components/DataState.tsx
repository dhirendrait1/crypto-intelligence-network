import type { DataState } from "../lib/api";

const labels: Record<DataState, string> = {
  fresh: "FRESH", stale: "STALE", partial: "PARTIAL", conflicting: "CONFLICTING",
  unavailable: "UNAVAILABLE", unknown: "UNKNOWN", error: "ERROR",
};

export function DataStateBadge({ state }: { state: DataState }) {
  return <span className={`data-state state-${state}`} role="status" aria-label={`Data state: ${labels[state]}`}>{labels[state]}</span>;
}

export function DataStatePanel({ state, message, source, retrievedAt }: {
  state: DataState; message: string; source?: string | null; retrievedAt?: string | null;
}) {
  return (
    <section className="data-state-panel" aria-live="polite">
      <div className="data-state-heading"><strong>Data availability</strong><DataStateBadge state={state} /></div>
      <p>{message}</p>
      {source && <small>Source: {source}</small>}
      {retrievedAt && <small>API retrieval time: {retrievedAt}</small>}
    </section>
  );
}