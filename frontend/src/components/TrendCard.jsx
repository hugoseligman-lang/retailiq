export default function TrendCard({ live, prev, trend }) {
  const dir   = trend > 0 ? "up" : trend < 0 ? "down" : "flat";
  const arrow = trend > 0 ? "↑" : trend < 0 ? "↓" : "→";
  const label = trend > 0
    ? `Up ${trend} since last scan`
    : trend < 0
    ? `Down ${Math.abs(trend)} since last scan`
    : "Holding steady";

  const prevCount = prev?.people_count ?? live.people_count;
  const pct = prevCount > 0
    ? Math.round(Math.abs(trend) / prevCount * 100)
    : 0;

  return (
    <div className="card">
      <div className="card-title">Occupancy Trend</div>
      <div className="trend-row">
        <div>
          <div className={`trend-pct ${dir}`}>
            {arrow} {pct}%
          </div>
          <div className="trend-label" style={{ marginTop: 4 }}>{label}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "0.68rem", color: "#A8A29E", marginBottom: 2 }}>Current</div>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: "#292524", lineHeight: 1 }}>
            {live.people_count}
          </div>
          <div style={{ fontSize: "0.68rem", color: "#A8A29E", marginTop: 4 }}>
            Prev: {prevCount}
          </div>
        </div>
      </div>
    </div>
  );
}
