export default function ZoneHeatmap({ zones }) {
  const left   = zones?.total_left   ?? 0;
  const center = zones?.total_center ?? 0;
  const right  = zones?.total_right  ?? 0;
  const max    = Math.max(left, center, right, 1);

  const bars = [
    { key: "left",   label: "Left",   value: left,   cls: "left"   },
    { key: "center", label: "Centre", value: center, cls: "center" },
    { key: "right",  label: "Right",  value: right,  cls: "right"  },
  ];

  return (
    <div className="card">
      <div className="card-title">Zone Activity — Today</div>
      <div className="zones-row">
        {bars.map((b) => (
          <div className="zone-bar-wrap" key={b.key}>
            <div className="zone-count">{b.value}</div>
            <div
              className={`zone-bar ${b.cls}`}
              style={{ height: `${Math.round((b.value / max) * 80)}px` }}
            />
            <div className="zone-name">{b.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
