export default function ActivityFeed({ feed }) {
  if (!feed?.length) {
    return (
      <div className="card">
        <div className="card-title">Recent Detections</div>
        <div style={{ color: "#A8A29E", fontSize: "0.78rem", marginTop: 8 }}>
          Waiting for data…
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-title">Recent Detections</div>
      <div className="feed-list">
        {feed.map((row, i) => {
          const count = row.people_count;
          const badge = count >= 5 ? "high" : count >= 2 ? "medium" : "low";
          const label = count >= 5 ? "Busy" : count >= 2 ? "Active" : "Quiet";
          const time  = new Date(row.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
          return (
            <div className="feed-item" key={i}>
              <span className="feed-time">{time}</span>
              <span className="feed-count">{count} {count === 1 ? "person" : "people"}</span>
              <span className="feed-zones">
                L{row.zone_left} C{row.zone_center} R{row.zone_right}
              </span>
              <span className={`feed-badge ${badge}`}>{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
