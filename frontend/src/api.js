const BASE = "/api";

async function get(path) {
  const r = await fetch(BASE + path);
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
  return r.json();
}

async function post(path, body) {
  const r = await fetch(BASE + path, {
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
};
