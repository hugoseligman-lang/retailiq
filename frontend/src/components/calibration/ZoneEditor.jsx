/**
 * ZoneEditor — SVG overlay on a camera frame.
 * Zones are stored/returned as percentage coords (0–100).
 * Supports drag-to-move, corner-handle resize, add, delete, rename.
 */
import { useState, useRef } from "react";

const TYPE_COLORS = {
  entrance:      { fill: "rgba(16,185,129,0.20)",  stroke: "#10B981" },
  counter_queue: { fill: "rgba(239,68,68,0.20)",   stroke: "#EF4444" },
  seating:       { fill: "rgba(59,130,246,0.20)",  stroke: "#3B82F6" },
  browsing:      { fill: "rgba(245,158,11,0.20)",  stroke: "#F59E0B" },
  custom:        { fill: "rgba(139,92,246,0.20)",  stroke: "#8B5CF6" },
};

const HANDLES = [
  { id: "nw", cx: 0,   cy: 0   },
  { id: "ne", cx: 1,   cy: 0   },
  { id: "sw", cx: 0,   cy: 1   },
  { id: "se", cx: 1,   cy: 1   },
];

let _uid = 1;
function uid() { return _uid++; }

export default function ZoneEditor({
  frameB64,
  frameWidth  = 1920,
  frameHeight = 1080,
  zones,
  entranceLine,
  onZonesChange,
  onEntranceLineChange,
}) {
  const svgRef     = useRef(null);
  const [sel, setSel]       = useState(null);   // selected zone id
  const [drag, setDrag]     = useState(null);   // { id, ox, oy, z0 }
  const [resize, setResize] = useState(null);   // { id, handle, z0 }
  const [lineDrag, setLineDrag] = useState(null); // { point: 'p1'|'p2'|'line', ox, oy, l0 }
  const [renaming, setRenaming] = useState(null);
  const [newLabel, setNewLabel] = useState("");

  // ── SVG coords ─────────────────────────────────────────────────────────────
  function svgCoords(e) {
    const svg  = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const rect = svg.getBoundingClientRect();
    return {
      x: ((e.clientX - rect.left) / rect.width)  * 100,
      y: ((e.clientY - rect.top)  / rect.height) * 100,
    };
  }

  // ── Zone drag ──────────────────────────────────────────────────────────────
  function onZoneDown(e, id) {
    e.stopPropagation();
    const c = svgCoords(e);
    setSel(id);
    setDrag({ id, ox: c.x, oy: c.y, z0: zones.find(z => z.id === id) });
  }

  // ── Handle resize ──────────────────────────────────────────────────────────
  function onHandleDown(e, id, handle) {
    e.stopPropagation();
    setResize({ id, handle, z0: zones.find(z => z.id === id) });
  }

  // ── SVG mouse move ─────────────────────────────────────────────────────────
  function onMouseMove(e) {
    const c = svgCoords(e);

    if (drag) {
      const dx = c.x - drag.ox, dy = c.y - drag.oy;
      const z  = drag.z0;
      const w  = z.x2_pct - z.x1_pct, h = z.y2_pct - z.y1_pct;
      const nx1 = Math.max(0, Math.min(z.x1_pct + dx, 100 - w));
      const ny1 = Math.max(0, Math.min(z.y1_pct + dy, 100 - h));
      onZonesChange(zones.map(z2 => z2.id === drag.id
        ? { ...z2, x1_pct: nx1, y1_pct: ny1, x2_pct: nx1 + w, y2_pct: ny1 + h }
        : z2
      ));
    }

    if (resize) {
      const z = resize.z0;
      let nx1 = z.x1_pct, ny1 = z.y1_pct, nx2 = z.x2_pct, ny2 = z.y2_pct;
      const MIN = 5;
      if (resize.handle === "nw") { nx1 = Math.min(c.x, z.x2_pct - MIN); ny1 = Math.min(c.y, z.y2_pct - MIN); }
      if (resize.handle === "ne") { nx2 = Math.max(c.x, z.x1_pct + MIN); ny1 = Math.min(c.y, z.y2_pct - MIN); }
      if (resize.handle === "sw") { nx1 = Math.min(c.x, z.x2_pct - MIN); ny2 = Math.max(c.y, z.y1_pct + MIN); }
      if (resize.handle === "se") { nx2 = Math.max(c.x, z.x1_pct + MIN); ny2 = Math.max(c.y, z.y1_pct + MIN); }
      onZonesChange(zones.map(z2 => z2.id === resize.id
        ? { ...z2, x1_pct: nx1, y1_pct: ny1, x2_pct: nx2, y2_pct: ny2 }
        : z2
      ));
    }

    if (lineDrag && entranceLine) {
      const dx = c.x - lineDrag.ox, dy = c.y - lineDrag.oy;
      const l  = lineDrag.l0;
      if (lineDrag.point === "p1") {
        onEntranceLineChange({ ...entranceLine, x1_pct: Math.max(0, Math.min(l.x1_pct + dx, 100)), y1_pct: Math.max(0, Math.min(l.y1_pct + dy, 100)) });
      } else if (lineDrag.point === "p2") {
        onEntranceLineChange({ ...entranceLine, x2_pct: Math.max(0, Math.min(l.x2_pct + dx, 100)), y2_pct: Math.max(0, Math.min(l.y2_pct + dy, 100)) });
      } else {
        onEntranceLineChange({ ...entranceLine, x1_pct: Math.max(0, Math.min(l.x1_pct + dx, 100)), y1_pct: Math.max(0, Math.min(l.y1_pct + dy, 100)), x2_pct: Math.max(0, Math.min(l.x2_pct + dx, 100)), y2_pct: Math.max(0, Math.min(l.y2_pct + dy, 100)) });
      }
    }
  }

  function onMouseUp() {
    setDrag(null);
    setResize(null);
    setLineDrag(null);
  }

  // ── Add zone ───────────────────────────────────────────────────────────────
  function addZone() {
    const z = { id: uid(), zone_type: "custom", label: "New Zone", x1_pct: 20, y1_pct: 20, x2_pct: 70, y2_pct: 70, confidence: 1.0 };
    onZonesChange([...zones, z]);
    setSel(z.id);
  }

  function deleteZone(id) {
    onZonesChange(zones.filter(z => z.id !== id));
    if (sel === id) setSel(null);
  }

  function startRename(id, current) {
    setRenaming(id);
    setNewLabel(current);
  }

  function commitRename() {
    if (renaming) {
      onZonesChange(zones.map(z => z.id === renaming ? { ...z, label: newLabel || z.label } : z));
      setRenaming(null);
    }
  }

  function cycleType(id) {
    const types = Object.keys(TYPE_COLORS);
    onZonesChange(zones.map(z => {
      if (z.id !== id) return z;
      const idx = (types.indexOf(z.zone_type) + 1) % types.length;
      return { ...z, zone_type: types[idx] };
    }));
  }

  const aspectPct = `${(frameHeight / frameWidth) * 100}%`;

  return (
    <div className="ze-root">
      {/* Toolbar */}
      <div className="ze-toolbar">
        <button className="ze-btn" onClick={addZone}>+ Add Zone</button>
        {sel != null && (<>
          <button className="ze-btn" onClick={() => { const z = zones.find(z => z.id === sel); if (z) startRename(z.id, z.label); }}>Rename</button>
          <button className="ze-btn" onClick={() => cycleType(sel)}>Change Type</button>
          <button className="ze-btn ze-btn-danger" onClick={() => deleteZone(sel)}>Delete</button>
        </>)}
        <div className="ze-legend">
          {Object.entries(TYPE_COLORS).map(([t, c]) => (
            <span key={t} className="ze-legend-item">
              <span className="ze-swatch" style={{ background: c.stroke }} />
              {t.replace("_", " ")}
            </span>
          ))}
        </div>
      </div>

      {/* Rename input */}
      {renaming != null && (
        <div className="ze-rename-bar">
          <input className="ze-rename-input" value={newLabel} autoFocus onChange={e => setNewLabel(e.target.value)} onKeyDown={e => { if (e.key === "Enter") commitRename(); if (e.key === "Escape") setRenaming(null); }} />
          <button className="ze-btn" onClick={commitRename}>OK</button>
        </div>
      )}

      {/* Frame + SVG overlay */}
      <div className="ze-frame-wrap" style={{ paddingBottom: aspectPct }}>
        {frameB64 && (
          <img
            className="ze-frame-img"
            src={`data:image/jpeg;base64,${frameB64}`}
            alt="camera frame"
          />
        )}
        {!frameB64 && <div className="ze-frame-placeholder">No frame available</div>}

        <svg
          ref={svgRef}
          className="ze-svg"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
          onClick={() => setSel(null)}
          style={{ cursor: drag || resize || lineDrag ? "grabbing" : "default" }}
        >
          {/* Zones */}
          {zones.map(z => {
            const col = TYPE_COLORS[z.zone_type] || TYPE_COLORS.custom;
            const isSelected = sel === z.id;
            const w = z.x2_pct - z.x1_pct, h = z.y2_pct - z.y1_pct;
            return (
              <g key={z.id}>
                <rect
                  x={z.x1_pct} y={z.y1_pct} width={w} height={h}
                  fill={col.fill} stroke={col.stroke}
                  strokeWidth={isSelected ? 0.6 : 0.3}
                  strokeDasharray={isSelected ? "none" : "2,1"}
                  style={{ cursor: "grab" }}
                  onMouseDown={e => onZoneDown(e, z.id)}
                  onClick={e => { e.stopPropagation(); setSel(z.id); }}
                />
                {/* Label */}
                <text x={z.x1_pct + w / 2} y={z.y1_pct + h / 2 - 2}
                  textAnchor="middle" dominantBaseline="middle"
                  fill="#fff" fontSize="3.5" fontWeight="700"
                  style={{ pointerEvents: "none", userSelect: "none", textShadow: "0 1px 3px #000" }}>
                  {z.label}
                </text>
                {/* Confidence */}
                <text x={z.x1_pct + w / 2} y={z.y1_pct + h / 2 + 3}
                  textAnchor="middle" dominantBaseline="middle"
                  fill={z.confidence < 0.6 ? "#EF4444" : "rgba(255,255,255,0.7)"} fontSize="2.8"
                  style={{ pointerEvents: "none", userSelect: "none" }}>
                  {Math.round((z.confidence || 1) * 100)}%{z.confidence < 0.6 ? " ⚠" : ""}
                </text>
                {/* Resize handles */}
                {isSelected && HANDLES.map(hd => (
                  <rect key={hd.id}
                    x={z.x1_pct + hd.cx * w - 1.5} y={z.y1_pct + hd.cy * h - 1.5}
                    width={3} height={3}
                    fill="#fff" stroke={col.stroke} strokeWidth={0.3}
                    style={{ cursor: "nwse-resize" }}
                    onMouseDown={e => { e.stopPropagation(); onHandleDown(e, z.id, hd.id); }}
                  />
                ))}
              </g>
            );
          })}

          {/* Entrance line */}
          {entranceLine && (() => {
            const l = entranceLine;
            return (
              <g>
                <line x1={l.x1_pct} y1={l.y1_pct} x2={l.x2_pct} y2={l.y2_pct}
                  stroke="#10B981" strokeWidth="0.6" strokeDasharray="3,1.5"
                  style={{ cursor: "grab" }}
                  onMouseDown={e => { e.stopPropagation(); const c = svgCoords(e); setLineDrag({ point: "line", ox: c.x, oy: c.y, l0: { ...l } }); }}
                />
                {/* Label */}
                <text x={(l.x1_pct + l.x2_pct) / 2} y={(l.y1_pct + l.y2_pct) / 2 - 2}
                  textAnchor="middle" fill="#10B981" fontSize="3" fontWeight="700"
                  style={{ pointerEvents: "none" }}>
                  Entrance ↕
                </text>
                {/* Endpoints */}
                {[{ key: "p1", cx: l.x1_pct, cy: l.y1_pct }, { key: "p2", cx: l.x2_pct, cy: l.y2_pct }].map(p => (
                  <circle key={p.key} cx={p.cx} cy={p.cy} r={2}
                    fill="#10B981" stroke="#fff" strokeWidth={0.3}
                    style={{ cursor: "grab" }}
                    onMouseDown={e => { e.stopPropagation(); const c = svgCoords(e); setLineDrag({ point: p.key, ox: c.x, oy: c.y, l0: { ...l } }); }}
                  />
                ))}
              </g>
            );
          })()}
        </svg>
      </div>
    </div>
  );
}
