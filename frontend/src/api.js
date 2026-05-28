// In dev (Vite proxy) uses /api → localhost:5050.
// In production (Vercel), customers store their backend URL in localStorage.
function base() {
  try {
    return localStorage.getItem("iq_backend") || "/api";
  } catch {
    return "/api";
  }
}

export function setBackend(url) {
  localStorage.setItem("iq_backend", url.replace(/\/+$/, "") + "/api");
}

async function get(path) {
  const r = await fetch(base() + path);
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
  return r.json();
}

async function post(path, body) {
  const r = await fetch(base() + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`POST ${path} → ${r.status}`);
  return r.json();
}

export const api = {
  live:            ()        => get("/live"),
  today:           ()        => get("/today"),
  traffic:         (overlay) => get(`/traffic?overlay=${overlay || "none"}`),
  heatmap:         (period)  => get(`/heatmap?period=${period || "today"}`),
  weather:         ()        => get("/weather"),
  insights:        ()        => get("/insights"),
  refreshInsights: ()        => post("/insights/refresh", {}),
  summary:         ()        => get("/summary"),
  generateSummary: ()        => post("/summary/generate", {}),
  chatHistory:     ()        => get("/chat/history"),
  chat:            (message) => post("/chat", { message }),
  config:          ()        => get("/config"),
  health:          ()        => get("/health"),
  setupStatus:     ()        => get("/setup/status"),
  submitSetup:     (data)    => post("/setup", data),
  geocode:         (q)       => get(`/setup/geocode?q=${encodeURIComponent(q)}`),

  // Live tracker
  trackerCounts:   ()      => get("/tracker/counts"),
  trackerSetLine:  (y)     => post("/tracker/line", { y }),
  trackerReset:    ()      => post("/tracker/reset", {}),
  streamUrl:       ()      => (base() + "/stream"),

  // Staff check-in / check-out
  staffIn:         ()      => post("/staff/in",  {}),
  staffOut:        ()      => post("/staff/out", {}),

  // Arlo camera auth
  arloConnect:     (email, password)       => post("/arlo/connect", { email, password }),
  arloVerify:      (session_id, code)      => post("/arlo/verify", { session_id, code }),
  arloSnapshot:    (session_id, device_id) => get(`/arlo/snapshot/${session_id}/${device_id}`),

  // Calibration
  calibData:           ()              => get("/calibration/data"),
  calibScanStart:      ()              => post("/calibration/scan/start", {}),
  calibScanStatus:     ()              => get("/calibration/scan/status"),
  calibTestCamera:     (mode, source)  => post("/calibration/camera/test", { mode, source }),
  calibAddCamera:      (d)             => post("/calibration/camera/add", d),
  calibCameras:        ()              => get("/calibration/cameras"),
  calibDeleteCamera:   (id)            => fetch(base() + `/calibration/camera/${id}`, { method: "DELETE" }).then(r => r.json()),
  calibAnalyse:        (camId)         => post(`/calibration/analyse/${camId}`, {}),
  calibSaveZones:      (camId, zones)  => post("/calibration/zones/save", { camera_id: camId, zones }),
  calibSaveEntrance:   (camId, line)   => post("/calibration/entrance/save", { camera_id: camId, line }),
  calibSaveQueue:      (camId, cfg)    => post("/calibration/queue/save", { camera_id: camId, ...cfg }),
  calibCrossRef:       (ids)           => post("/calibration/cross-reference", { camera_ids: ids }),
  calibTestStart:      (type, camId, dur) => post("/calibration/test/start", { type, camera_id: camId, duration: dur }),
  calibTestStatus:     ()              => get("/calibration/test/status"),
  calibComplete:       ()              => post("/calibration/complete", {}),
};
