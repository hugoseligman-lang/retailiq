import { useState, useEffect } from "react";
import { api } from "../api";

/**
 * CafeActivity — replaces the generic Left/Centre/Right heatmap.
 * Shows café-relevant metrics: door traffic vs POS queue activity by hour.
 */
export default function HeatmapGrid() {
  const [period,  setPeriod]  = useState("today");
  const [traffic, setTraffic] = useState(null);
  const [cameras, setCameras] = useState({});

  useEffect(() => {
    api.heatmap(period).then(setTraffic).catch(() => {});
    api.camerasStatus().then(setCameras).catch(() => {});
  }, [period]);

  const hourly = traffic?.hourly || [];
  const maxVal = Math.max(...hourly.map(h => h.avg_count || 0), 1);

  // Per-camera totals from camera status
  const frontCam = cameras.front || {};
  const posCam   = cameras.pos   || {};

  return (
    <div className="card cafe-activity-card">
      <div className="section-header" style={{ marginBottom: 12 }}>
        <div className="card-label" style={{ marginBottom: 0 }}>Store Activity</div>
        <div className="heatmap-toggle">
          {["today","week","month"].map(p => (
            <button key={p} className={`toggle-btn ${period===p?"active":""}`} onClick={() => setPeriod(p)}>
              {p==="today" ? "Today" : p==="week" ? "7 Days" : "30 Days"}
            </button>
          ))}
        </div>
      </div>

      {/* ── Zone summary cards ── */}
      <div className="cafe-zone-row">
        <div className="cafe-zone-card">
          <div className="cafe-zone-icon">🚪</div>
          <div className="cafe-zone-name">Front Door</div>
          <div className="cafe-zone-stat">
            <span className="cafe-zone-val green">{frontCam.entries ?? "—"}</span>
            <span className="cafe-zone-sub">entries</span>
          </div>
          <div className="cafe-zone-stat">
            <span className="cafe-zone-val amber">{frontCam.exits ?? "—"}</span>
            <span className="cafe-zone-sub">exits</span>
          </div>
          <div className={`cafe-zone-status ${frontCam.fresh ? "live" : "offline"}`}>
            {frontCam.fresh ? "● live" : "○ offline"}
          </div>
        </div>

        <div className="cafe-zone-card">
          <div className="cafe-zone-icon">🛒</div>
          <div className="cafe-zone-name">POS Counter</div>
          <div className="cafe-zone-stat">
            <span className="cafe-zone-val" style={{ color: (posCam.queue_length ?? 0) >= 3 ? "var(--red)" : "var(--green)" }}>
              {posCam.queue_length ?? "—"}
            </span>
            <span className="cafe-zone-sub">queuing now</span>
          </div>
          <div className="cafe-zone-stat">
            <span className="cafe-zone-val amber">{posCam.queue_events ?? "—"}</span>
            <span className="cafe-zone-sub">queue events</span>
          </div>
          <div className={`cafe-zone-status ${posCam.fresh ? "live" : "offline"}`}>
            {posCam.fresh ? "● live" : "○ offline"}
          </div>
        </div>
      </div>

      {/* ── Hourly traffic bar chart ── */}
      {hourly.length > 0 && (
        <div className="cafe-hourly-wrap">
          <div className="cafe-hourly-label">Traffic by Hour</div>
          <div className="cafe-hourly-bars">
            {hourly.map((h, i) => {
              const pct = Math.round((h.avg_count / maxVal) * 100);
              const isNow = new Date().getHours() === parseInt(h.hour);
              return (
                <div key={i} className={`cafe-hour-col ${isNow ? "now" : ""}`} title={`${h.hour}:00 — avg ${h.avg_count?.toFixed(1)} people`}>
                  <div className="cafe-hour-bar-wrap">
                    <div className="cafe-hour-bar" style={{ height: `${Math.max(pct, 2)}%` }} />
                  </div>
                  {i % 3 === 0 && <div className="cafe-hour-tick">{h.hour}</div>}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
