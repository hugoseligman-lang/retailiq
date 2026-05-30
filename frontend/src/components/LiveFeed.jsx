import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "../api";

const ROLES = {
  front: { label: "Front Door",  icon: "🚪", mode: "crossing" },
  back:  { label: "Back Door",   icon: "🚪", mode: "crossing" },
  pos:   { label: "POS Counter", icon: "🛒", mode: "queue"    },
};

export default function LiveFeed() {
  const [cameras,  setCameras]  = useState({});   // from /api/cameras/status
  const [counts,   setCounts]   = useState({});   // merged + per-camera
  const [lineYs,   setLineYs]   = useState({});   // per-camera line position
  const [dragging, setDragging] = useState(null); // role being dragged

  const imgRefs = useRef({});
  const pollRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [cams, merged] = await Promise.all([
        api.camerasStatus(),
        api.trackerMerged().catch(() => ({})),
      ]);
      setCameras(cams || {});
      setCounts(merged || {});
    } catch { /* offline */ }
  }, []);

  useEffect(() => {
    refresh();
    pollRef.current = setInterval(refresh, 2000);
    return () => clearInterval(pollRef.current);
  }, [refresh]);

  const activeCameras = Object.entries(cameras).filter(([, c]) => c.fresh);
  const hasAny        = activeCameras.length > 0;

  const handleLineDrag = useCallback(async (role, e) => {
    if (dragging !== role) return;
    const el = imgRefs.current[role];
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const y = Math.max(0.1, Math.min(0.9, (e.clientY - rect.top) / rect.height));
    setLineYs(prev => ({ ...prev, [role]: y }));
    try { await api.trackerSetLine(y); } catch { /* ignore */ }
  }, [dragging]);

  const handleReset = async () => {
    await api.trackerReset().catch(() => {});
    refresh();
  };

  if (!hasAny) {
    return (
      <div className="livefeed-root livefeed-empty">
        <div className="livefeed-empty-icon">📷</div>
        <div className="livefeed-empty-title">No cameras streaming yet</div>
        <div className="livefeed-empty-sub">
          Start the Raspberry Pi bridge at the café, or open{" "}
          <a href="/camera">cafe.meridianai.build/camera</a> on a phone to stream manually.
        </div>
      </div>
    );
  }

  return (
    <div className="livefeed-root">
      {/* ── Camera grid ──────────────────────────────────────────────── */}
      <div className={`livefeed-cam-grid livefeed-cam-grid-${activeCameras.length}`}>
        {activeCameras.map(([role, cam]) => {
          const meta   = ROLES[role] || { label: role, icon: "📷", mode: "crossing" };
          const lineY  = lineYs[role] ?? 0.55;
          const perCam = counts?.cameras?.[role] || {};

          return (
            <div key={role} className="livefeed-cam-card">
              {/* Label bar */}
              <div className="livefeed-cam-label">
                <span className="livefeed-cam-dot" />
                {meta.icon} {meta.label}
                <span className="livefeed-cam-age">{cam.age_seconds != null ? `${Math.round(cam.age_seconds)}s ago` : ""}</span>
              </div>

              {/* Stream */}
              <div
                className="livefeed-video-wrap"
                onMouseMove={e => handleLineDrag(role, e)}
                onMouseUp={() => setDragging(null)}
                onMouseLeave={() => setDragging(null)}
              >
                <img
                  ref={el => imgRefs.current[role] = el}
                  src={api.streamUrl(role)}
                  alt={meta.label}
                  className="livefeed-img"
                  draggable={false}
                />

                {/* Entrance line — door cameras only */}
                {meta.mode === "crossing" && (
                  <>
                    <div
                      className="livefeed-line-handle"
                      style={{ top: `${lineY * 100}%` }}
                      onMouseDown={e => { e.preventDefault(); setDragging(role); }}
                      title="Drag to set entrance line"
                    />
                    <div className="livefeed-label-enter" style={{ top: `calc(${lineY * 100}% + 14px)` }}>▼ ENTER</div>
                    <div className="livefeed-label-exit"  style={{ top: `calc(${lineY * 100}% - 22px)` }}>▲ EXIT</div>
                    <div className="livefeed-drag-hint">drag line to reposition</div>
                  </>
                )}

                {/* Queue badge — POS camera */}
                {meta.mode === "queue" && (perCam.queue_length ?? 0) > 0 && (
                  <div className="livefeed-queue-badge">
                    🛒 Queue: {perCam.queue_length}
                  </div>
                )}
              </div>

              {/* Per-camera stats */}
              <div className="livefeed-cam-stats">
                {meta.mode === "crossing" ? (
                  <>
                    <CamStat label="In"    value={perCam.entries   ?? 0} colour="var(--green)" />
                    <CamStat label="Out"   value={perCam.exits     ?? 0} colour="var(--amber)" />
                    <CamStat label="Passed" value={perCam.passersby ?? 0} colour="var(--muted)" />
                    {(perCam.entries ?? 0) + (perCam.passersby ?? 0) > 0 && (
                      <CamStat
                        label="Conv."
                        value={`${Math.round((perCam.entries ?? 0) / ((perCam.entries ?? 0) + (perCam.passersby ?? 0)) * 100)}%`}
                        colour="var(--blue)"
                      />
                    )}
                  </>
                ) : (
                  <>
                    <CamStat label="Queue Now"    value={perCam.queue_length ?? 0} colour={perCam.queue_length >= 3 ? "var(--red)" : "var(--green)"} />
                    <CamStat label="Queue Events" value={perCam.queue_events ?? 0} colour="var(--amber)" />
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Merged totals bar ─────────────────────────────────────────── */}
      <div className="livefeed-totals-bar">
        <div className="livefeed-total-item">
          <span className="livefeed-total-label">Total In Store</span>
          <span className="livefeed-total-val green">{counts.in_store ?? 0}</span>
        </div>
        <div className="livefeed-total-item">
          <span className="livefeed-total-label">Entries Today</span>
          <span className="livefeed-total-val">{counts.entries ?? 0}</span>
        </div>
        <div className="livefeed-total-item">
          <span className="livefeed-total-label">Queue Now</span>
          <span className="livefeed-total-val amber">{counts.queue_length ?? 0}</span>
        </div>
        <div className="livefeed-total-item">
          <span className="livefeed-total-label">Conversion</span>
          <span className="livefeed-total-val blue">
            {counts.entries + counts.passersby > 0
              ? `${Math.round(counts.entries / (counts.entries + counts.passersby) * 100)}%`
              : "—"}
          </span>
        </div>
        <button className="livefeed-reset-btn" onClick={handleReset}>Reset counts</button>
      </div>
    </div>
  );
}

function CamStat({ label, value, colour }) {
  return (
    <div className="livefeed-cam-stat">
      <div className="livefeed-cam-stat-label">{label}</div>
      <div className="livefeed-cam-stat-val" style={{ color: colour }}>{value}</div>
    </div>
  );
}
