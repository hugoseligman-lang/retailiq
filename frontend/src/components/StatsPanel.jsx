export default function StatsPanel({ stats }) {
  const items = [
    { label: "Total Detections Today", value: stats?.total_detections ?? "—" },
    { label: "Peak Count",             value: stats?.peak_count       ?? "—" },
    { label: "Peak Hour",              value: stats?.peak_hour        ?? "—" },
    { label: "Zones Tracked",          value: "3" },
  ];

  return (
    <div className="card">
      <div className="card-title">Today's Summary</div>
      <div className="stats-grid">
        {items.map((s) => (
          <div className="stat-item" key={s.label}>
            <div className="stat-value">{s.value}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
