export default function LiveCount({ count, lastUpdated, online }) {
  const time = lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : "—";

  return (
    <div className="card live-count-card">
      <div className="card-title">Live Count</div>
      <div className="live-number">{count ?? 0}</div>
      <div className="live-label">people in store</div>
      <div className="live-updated">Last updated {time}</div>
    </div>
  );
}
