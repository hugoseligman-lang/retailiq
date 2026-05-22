export default function ZoneHeatmap({ zones, totalZone }) {
  const left   = zones?.total_left   ?? 0;
  const center = zones?.total_center ?? 0;
  const right  = zones?.total_right  ?? 0;
  const max    = Math.max(left, center, right, 1);

  const bars = [
    { key: "left",   label: "Left",   value: left,   cls: "left",   color: "#FBBF24" },
    { key: "center", label: "Centre", value: center, cls: "center", color: "#F59E0B" },
    { key: "right",  label: "Right",  value: right,  cls: "right",  color: "#F97316" },
  ];

  return (
    <div className="card">
      <div className="card-title">Zone Activity — Today</div>
      <div className="zones-grid">
        {bars.map(b => {
          const pct = totalZone ? Math.round(b.value / totalZone * 100) : 0;
          return (
            <div className="zone-col" key={b.key}>
              <div className="zone-pct">{pct}%</div>
              <div className="zone-count">{b.value}</div>
              <div
                className={`zone-bar ${b.cls}`}
                style={{ height: `${Math.round((b.value / max) * 72)}px` }}
              />
              <div className="zone-name">{b.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
