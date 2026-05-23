function cvClass(pct) {
  if (pct >= 30) return "conversion-good";
  if (pct >= 15) return "conversion-mid";
  return "conversion-low";
}

export default function TodayStats({ stats }) {
  const s = stats || {};
  const cv = s.conversion_rate ?? 0;

  const tiles = [
    { label: "Total Visitors",     value: s.total_visitors   ?? "—", sub: "in-store today" },
    { label: "Passersby",          value: s.total_passersby  ?? "—", sub: "detected outside" },
    { label: "Conversion Rate",    value: `${cv}%`,                   sub: "visitors / (visitors+passersby)", cls: cvClass(cv) },
    { label: "Peak 30-Min Window", value: s.peak_window      ?? "—", sub: "busiest half-hour" },
    { label: "Avg Zone Left",      value: s.avg_zone_left    ?? "—", sub: "avg people" },
    { label: "Avg Zone Centre",    value: s.avg_zone_center  ?? "—", sub: "avg people" },
    { label: "Avg Zone Right",     value: s.avg_zone_right   ?? "—", sub: "avg people" },
    { label: "Queue Events",       value: s.queue_events     ?? "—", sub: "times queue formed" },
    { label: "Longest Queue",      value: s.longest_queue    ?? "—", sub: "people at once" },
    { label: "Avg Queue Length",   value: s.avg_queue != null ? Number(s.avg_queue).toFixed(1) : "—", sub: "when queuing" },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 14, marginBottom: 18 }}>
      {tiles.map(t => (
        <div className="card" key={t.label}>
          <div className="stat-lbl">{t.label}</div>
          <div className={`stat-val ${t.cls || ""}`}>{t.value}</div>
          <div className="stat-sub">{t.sub}</div>
        </div>
      ))}
    </div>
  );
}
