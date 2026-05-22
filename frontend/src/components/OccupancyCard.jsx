export default function OccupancyCard({ live, stats }) {
  const peak    = stats?.peak_count ?? 0;
  const current = live?.people_count ?? 0;
  // Use peak or a sensible max (e.g. 20) for the gauge
  const max     = Math.max(peak, current, 1);
  const pct     = Math.min(Math.round((current / max) * 100), 100);

  const label = pct >= 80 ? "Near Peak" : pct >= 50 ? "Moderate" : "Low";
  const color  = pct >= 80 ? "#F97316" : pct >= 50 ? "#F59E0B" : "#FBBF24";

  return (
    <div className="card">
      <div className="card-title">Current vs Peak</div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: "#292524", lineHeight: 1 }}>{current}</div>
          <div style={{ fontSize: "0.7rem", color: "#A8A29E", marginTop: 3 }}>Current</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#F59E0B" }}>{peak}</div>
          <div style={{ fontSize: "0.7rem", color: "#A8A29E", marginTop: 3 }}>Today's Peak</div>
        </div>
      </div>
      <div className="occ-bar-wrap">
        <div className="occ-bar-track">
          <div className="occ-bar-fill" style={{ width: `${pct}%`, background: color }} />
        </div>
        <div className="occ-labels">
          <span>{pct}% of peak</span>
          <span style={{ color, fontWeight: 700 }}>{label}</span>
        </div>
      </div>
    </div>
  );
}
