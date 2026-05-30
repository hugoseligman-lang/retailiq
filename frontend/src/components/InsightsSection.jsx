import { useState } from "react";
import { api } from "../api";

export default function InsightsSection({ insights, onRefresh }) {
  const [loading, setLoading] = useState(false);

  async function handleRefresh() {
    setLoading(true);
    try { await onRefresh(); } finally { setLoading(false); }
  }

  const ins = insights || {};
  const summary      = ins.summary      || "";
  const zoneAnalysis = ins.zone_analysis || "";
  const weatherNote  = ins.weather_note  || "";
  const patterns     = ins.patterns      || [];
  const anomalies    = ins.anomalies     || [];
  const alerts       = ins.alerts        || [];

  const hasData = summary || patterns.length || anomalies.length || alerts.length || zoneAnalysis;

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Section 2 — AI Analysis</div>
        <button className="refresh-btn" onClick={handleRefresh} disabled={loading}>
          {loading ? "Analysing…" : "↻ Refresh"}
        </button>
      </div>

      {!hasData ? (
        <div className="card insights-empty">
          No AI insights yet — click Refresh to generate your first analysis.
        </div>
      ) : (
        <div className="insights-stack">

          {/* Narrative summary — always first */}
          {summary && (
            <div className="insight-summary-card">
              <div className="insight-summary-icon">🧠</div>
              <p className="insight-summary-text">{summary}</p>
            </div>
          )}

          {/* Weather note */}
          {weatherNote && (
            <div className="insight-weather-note">
              🌤 {weatherNote}
            </div>
          )}

          {/* Alerts — urgent */}
          {alerts.length > 0 && (
            <div className="insight-block">
              <div className="insight-block-title">⚠ Alerts</div>
              {alerts.map((a, i) => <div key={i} className="insight-item alert">{a}</div>)}
            </div>
          )}

          <div className="insights-grid">
            <div className="insights-col">
              {anomalies.length > 0 && (
                <div className="insight-block">
                  <div className="insight-block-title">Anomalies</div>
                  {anomalies.map((a, i) => <div key={i} className="insight-item anomaly">{a}</div>)}
                </div>
              )}
              {zoneAnalysis && (
                <div className="insight-block">
                  <div className="insight-block-title">📍 Zone Activity</div>
                  <div className="insight-item pattern">{zoneAnalysis}</div>
                </div>
              )}
            </div>
            <div className="insights-col">
              {patterns.length > 0 && (
                <div className="insight-block">
                  <div className="insight-block-title">Patterns</div>
                  {patterns.map((p, i) => <div key={i} className="insight-item pattern">{p}</div>)}
                </div>
              )}
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
