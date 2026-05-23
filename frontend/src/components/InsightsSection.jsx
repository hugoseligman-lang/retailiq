import { useState } from "react";
import { api } from "../api";

export default function InsightsSection({ insights, onRefresh }) {
  const [loading, setLoading] = useState(false);

  async function handleRefresh() {
    setLoading(true);
    try { await onRefresh(); } finally { setLoading(false); }
  }

  const ins = insights || {};
  const patterns   = ins.patterns   || [];
  const anomalies  = ins.anomalies  || [];
  const alerts     = ins.alerts     || [];
  const comp       = ins.comparisons || {};
  const compItems  = Object.entries(comp).filter(([, v]) => v);

  const hasData = patterns.length || anomalies.length || alerts.length || compItems.length;

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Section 2 — AI Pattern Analysis</div>
        <button className="refresh-btn" onClick={handleRefresh} disabled={loading}>
          {loading ? "Analysing…" : "↻ Refresh Now"}
        </button>
      </div>

      {!hasData ? (
        <div className="card insights-empty">
          No AI insights yet — runs automatically each hour, or click Refresh Now.
        </div>
      ) : (
        <div className="insights-grid">
          <div className="insights-col">
            {alerts.length > 0 && (
              <div className="insight-block">
                <div className="insight-block-title">⚠ Alerts</div>
                {alerts.map((a, i) => <div key={i} className="insight-item alert">{a}</div>)}
              </div>
            )}
            {anomalies.length > 0 && (
              <div className="insight-block">
                <div className="insight-block-title">Anomalies (&gt;25% from average)</div>
                {anomalies.map((a, i) => <div key={i} className="insight-item anomaly">{a}</div>)}
              </div>
            )}
          </div>
          <div className="insights-col">
            {patterns.length > 0 && (
              <div className="insight-block">
                <div className="insight-block-title">Recurring Patterns</div>
                {patterns.map((p, i) => <div key={i} className="insight-item pattern">{p}</div>)}
              </div>
            )}
            {compItems.length > 0 && (
              <div className="insight-block">
                <div className="insight-block-title">Period Comparisons</div>
                {compItems.map(([k, v]) => (
                  <div key={k} className="insight-item compare">
                    <strong>{k.replace(/_/g, " ")}:</strong> {v}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
