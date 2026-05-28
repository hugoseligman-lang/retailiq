import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "../api";

export default function LiveFeed() {
  const [counts, setCounts] = useState(null);
  const [lineY,  setLineY]  = useState(0.55);
  const [dragging, setDragging] = useState(false);
  const imgRef   = useRef(null);
  const pollRef  = useRef(null);

  // Stream URL — direct to backend (works dev + local install)
  const streamSrc = api.streamUrl();

  const fetchCounts = useCallback(async () => {
    try {
      const c = await api.trackerCounts();
      setCounts(c);
      setLineY(c.line_y ?? 0.55);
    } catch { /* backend offline */ }
  }, []);

  useEffect(() => {
    fetchCounts();
    pollRef.current = setInterval(fetchCounts, 1500);
    return () => clearInterval(pollRef.current);
  }, [fetchCounts]);

  const handleReset = async () => {
    await api.trackerReset();
    fetchCounts();
  };

  const handleLineDrag = async (e) => {
    if (!imgRef.current) return;
    const rect = imgRef.current.getBoundingClientRect();
    const y = Math.max(0.1, Math.min(0.9, (e.clientY - rect.top) / rect.height));
    setLineY(y);
    await api.trackerSetLine(y);
  };

  const c = counts || {};
  const entries   = c.entries   ?? 0;
  const exits     = c.exits     ?? 0;
  const passersby = c.passersby ?? 0;
  const inStore   = Math.max(0, c.in_store ?? 0);
  const conv      = c.conversion_rate ?? 0;

  return (
    <div className="livefeed-root">
      {/* ── Video stream ──────────────────────────────────────────────── */}
      <div
        className="livefeed-video-wrap"
        onMouseMove={dragging ? handleLineDrag : undefined}
        onMouseUp={() => setDragging(false)}
        onMouseLeave={() => setDragging(false)}
      >
        <img
          ref={imgRef}
          src={streamSrc}
          alt="Live feed"
          className="livefeed-img"
          draggable={false}
        />
        {/* Drag handle for line — shown as a thin strip you can grab */}
        <div
          className="livefeed-line-handle"
          style={{ top: `${lineY * 100}%` }}
          onMouseDown={(e) => { e.preventDefault(); setDragging(true); }}
          title="Drag to move entrance line"
        />
        <div className="livefeed-label-enter" style={{ top: `calc(${lineY * 100}% + 14px)` }}>
          ▼ ENTER
        </div>
        <div className="livefeed-label-exit" style={{ top: `calc(${lineY * 100}% - 22px)` }}>
          ▲ EXIT
        </div>
        <div className="livefeed-drag-hint">↕ drag line to reposition</div>
      </div>

      {/* ── Stats bar ──────────────────────────────────────────────────── */}
      <div className="livefeed-stats">
        <Stat label="In Store" value={inStore} colour="var(--blue)" />
        <Stat label="Entries" value={entries} colour="var(--green)" />
        <Stat label="Exits" value={exits} colour="var(--amber)" />
        <Stat label="Passersby" value={passersby} colour="var(--muted)" />

        {/* Conversion rate — big call-out */}
        <div className="livefeed-conv">
          <div className="livefeed-conv-label">Conversion Rate</div>
          <div className="livefeed-conv-value">{conv}%</div>
          <div className="livefeed-conv-sub">
            {entries} customer{entries !== 1 ? "s" : ""} of {entries + passersby} visitors
          </div>
          {/* Progress bar */}
          <div className="livefeed-conv-bar">
            <div className="livefeed-conv-fill" style={{ width: `${conv}%` }} />
          </div>
        </div>

        <button className="livefeed-reset-btn" onClick={handleReset}>
          ↺ Reset counts
        </button>
      </div>
    </div>
  );
}

function Stat({ label, value, colour }) {
  return (
    <div className="livefeed-stat">
      <div className="livefeed-stat-label">{label}</div>
      <div className="livefeed-stat-value" style={{ color: colour }}>{value}</div>
    </div>
  );
}
