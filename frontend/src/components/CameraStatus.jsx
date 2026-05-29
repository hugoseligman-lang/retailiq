/**
 * CameraStatus — shows the live status of every active camera feed.
 * Polls /api/cameras/status every 5 seconds.
 * Displayed in the LiveFeed section when multi-camera is active.
 */
import { useEffect, useState } from "react";
import { api } from "../api";

const ROLE_LABELS = { front: "Front Door", back: "Back Door", pos: "POS Counter", default: "Camera" };

export default function CameraStatus() {
  const [status, setStatus]   = useState(null);
  const [updated, setUpdated] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const s = await api.camerasStatus();
        if (!cancelled) {
          setStatus(s);
          setUpdated(new Date());
        }
      } catch { /* backend offline */ }
    }
    poll();
    const id = setInterval(poll, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (!status || !status.cameras || Object.keys(status.cameras).length === 0) {
    return null;  // Don't render in single-camera mode
  }

  const cameras    = status.cameras;
  const total      = status.total_cameras   || 0;
  const healthy    = status.healthy_cameras || 0;
  const allHealthy = healthy === total;

  return (
    <div className="cam-status-wrap">
      <div className="cam-status-header">
        <span className="cam-status-title">Camera Feeds</span>
        <span className={`cam-status-badge ${allHealthy ? "cam-badge-ok" : "cam-badge-warn"}`}>
          {healthy}/{total} live
        </span>
        {updated && (
          <span className="cam-status-updated">
            updated {updated.toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
          </span>
        )}
      </div>
      <div className="cam-status-grid">
        {Object.entries(cameras).map(([role, info]) => (
          <CameraCard key={role} role={role} info={info} />
        ))}
      </div>
    </div>
  );
}

function CameraCard({ role, info }) {
  const fresh   = info.fresh;
  const age     = info.age_seconds;
  const counts  = info.counts || {};
  const label   = ROLE_LABELS[role] || role;
  const mode    = counts.mode || "—";

  const ageText = age != null
    ? age < 5  ? "live"
    : age < 30 ? `${age}s ago`
    : `${Math.round(age)}s ago`
    : "never";

  return (
    <div className={`cam-card ${fresh ? "cam-card-ok" : "cam-card-dead"}`}>
      <div className="cam-card-header">
        <span className={`cam-dot ${fresh ? "cam-dot-ok" : "cam-dot-dead"}`} />
        <span className="cam-card-name">{label}</span>
        <span className="cam-card-mode">{mode}</span>
      </div>
      <div className="cam-card-age">{ageText}</div>
      {counts && (
        <div className="cam-card-counts">
          {mode === "queue" ? (
            <>
              <CamStat label="Queue"  value={counts.queue_length ?? "—"} />
              <CamStat label="Events" value={counts.queue_events  ?? "—"} />
            </>
          ) : (
            <>
              <CamStat label="In"   value={counts.in_store ?? "—"} />
              <CamStat label="Entries" value={counts.entries ?? "—"} />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function CamStat({ label, value }) {
  return (
    <div className="cam-stat">
      <span className="cam-stat-lbl">{label}</span>
      <span className="cam-stat-val">{value}</span>
    </div>
  );
}
