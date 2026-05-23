import { useState, useEffect } from "react";
import { api } from "../api";

function heatColor(pct) {
  // 0% → cold blue, 100% → hot red
  if (pct < 20) return { bg: "rgba(59,130,246,0.25)", border: "rgba(59,130,246,0.4)" };
  if (pct < 40) return { bg: "rgba(16,185,129,0.25)", border: "rgba(16,185,129,0.4)" };
  if (pct < 60) return { bg: "rgba(245,158,11,0.25)", border: "rgba(245,158,11,0.4)" };
  if (pct < 80) return { bg: "rgba(249,115,22,0.3)",  border: "rgba(249,115,22,0.5)" };
  return { bg: "rgba(239,68,68,0.35)", border: "rgba(239,68,68,0.55)" };
}

export default function HeatmapGrid() {
  const [period, setPeriod] = useState("today");
  const [data, setData]     = useState(null);

  useEffect(() => {
    api.heatmap(period).then(setData).catch(() => {});
  }, [period]);

  const left   = Number(data?.left_total   || 0);
  const center = Number(data?.center_total || 0);
  const right  = Number(data?.right_total  || 0);
  const total  = left + center + right || 1;

  const zones = [
    { name: "Left Zone",   val: left,   pct: Math.round(left   / total * 100) },
    { name: "Centre Zone", val: center, pct: Math.round(center / total * 100) },
    { name: "Right Zone",  val: right,  pct: Math.round(right  / total * 100) },
  ];

  return (
    <div className="card">
      <div className="section-header" style={{ marginBottom: 0 }}>
        <div className="card-label" style={{ marginBottom: 0 }}>Zone Heatmap</div>
        <div className="heatmap-toggle">
          {["today", "week", "month"].map(p => (
            <button key={p} className={`toggle-btn ${period === p ? "active" : ""}`}
              onClick={() => setPeriod(p)}>
              {p === "today" ? "Today" : p === "week" ? "7 Days" : "30 Days"}
            </button>
          ))}
        </div>
      </div>
      <div className="heatmap-grid">
        {zones.map(z => {
          const col = heatColor(z.pct);
          return (
            <div key={z.name} className="heatmap-cell"
              style={{ background: col.bg, border: `1px solid ${col.border}` }}>
              <div className="heatmap-cell-name">{z.name}</div>
              <div className="heatmap-cell-val">{z.val.toLocaleString()}</div>
              <div className="heatmap-cell-pct">{z.pct}% of traffic</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
