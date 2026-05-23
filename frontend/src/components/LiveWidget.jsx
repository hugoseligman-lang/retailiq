export default function LiveWidget({ live, weather }) {
  const people  = live?.people_count  ?? 0;
  const queue   = live?.queue_length  ?? 0;
  const left    = live?.zone_left     ?? 0;
  const center  = live?.zone_center   ?? 0;
  const right   = live?.zone_right    ?? 0;
  const busiest = live?.busiest_zone  ?? "none";
  const max     = Math.max(left, center, right, 1);

  const w = weather || {};
  const wStr = w.condition ? `${w.icon ?? ""} ${w.condition} · ${w.temperature}°C` : "—";

  return (
    <div className="live-grid">
      {/* People count */}
      <div className="card live-hero">
        <div className="card-label">In Store Now</div>
        <div className="card-value">{people}</div>
        <div className="card-sub">{wStr}</div>
      </div>

      {/* Queue */}
      <div className="card live-queue">
        <div className="card-label">Queue Length</div>
        <div className="card-value" style={{ color: queue >= 3 ? "var(--red)" : queue >= 1 ? "var(--amber)" : "var(--green)" }}>
          {queue}
        </div>
        <div className="card-sub">{queue === 0 ? "No queue" : queue === 1 ? "1 waiting" : `${queue} waiting`}</div>
      </div>

      {/* Zone heatmap */}
      <div className="card live-zone-card">
        <div className="zone-label">Zone Activity</div>
        <div className="zone-bars">
          {[
            { key: "left",   label: "Left",   val: left,   cls: "left" },
            { key: "center", label: "Centre", val: center, cls: "center" },
            { key: "right",  label: "Right",  val: right,  cls: "right" },
          ].map(z => (
            <div className="zone-bar-col" key={z.key}>
              <div className="zone-bar-count">{z.val}</div>
              <div
                className={`zone-bar-fill ${z.cls}`}
                style={{ height: `${Math.round((z.val / max) * 52)}px` }}
              />
              <div className="zone-bar-name">{z.label}</div>
            </div>
          ))}
        </div>
        {busiest !== "none" && (
          <div className="card-sub" style={{ marginTop: 8 }}>
            Busiest: <strong style={{ color: "var(--amber)" }}>{busiest}</strong> zone
          </div>
        )}
      </div>
    </div>
  );
}
