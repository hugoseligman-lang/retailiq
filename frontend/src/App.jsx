import { useEffect, useState, useCallback } from "react";
import { api } from "./api";
import LiveWidget      from "./components/LiveWidget";
import TodayStats      from "./components/TodayStats";
import HeatmapGrid     from "./components/HeatmapGrid";
import TrafficChart    from "./components/TrafficChart";
import InsightsSection from "./components/InsightsSection";
import DailySummary    from "./components/DailySummary";
import ChatInterface   from "./components/ChatInterface";

const REFRESH_MS = 30_000;

export default function App() {
  const [live,     setLive]     = useState(null);
  const [today,    setToday]    = useState(null);
  const [insights, setInsights] = useState(null);
  const [summary,  setSummary]  = useState(null);
  const [weather,  setWeather]  = useState(null);
  const [online,   setOnline]   = useState(false);
  const [store,    setStore]    = useState("RetailIQ");

  const refresh = useCallback(async () => {
    try {
      const [l, t, i, s, w, c] = await Promise.all([
        api.live(), api.today(), api.insights(),
        api.summary(), api.weather(), api.config(),
      ]);
      setLive(l);    setToday(t); setInsights(i);
      setSummary(s); setWeather(w);
      if (c?.store_name) setStore(c.store_name);
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const now = new Date();
  const dateStr = now.toLocaleDateString("en-AU", {
    weekday: "long", day: "numeric", month: "long", year: "numeric"
  });
  const timeStr = now.toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="shell">
      {/* ── Topbar ── */}
      <header className="topbar">
        <div className="topbar-logo"><span>Retail</span>IQ</div>
        <div className="topbar-meta">
          <span className="topbar-store">{store}</span>
          <span>{dateStr} · {timeStr}</span>
          {weather?.condition && (
            <span>{weather.icon} {weather.condition} · {weather.temperature}°C</span>
          )}
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span className={`live-dot ${online ? "" : "offline-dot"}`} />
            {online ? "Live" : "Offline"}
          </span>
        </div>
      </header>

      <main className="content">
        {/* ── Section 1: Raw Data ── */}
        <div className="section">
          <div className="section-header">
            <div className="section-title">Section 1 — Live &amp; Raw Data</div>
          </div>

          <LiveWidget live={live} weather={weather} />
          <TodayStats stats={today} />

          <div className="bottom-row">
            <TrafficChart />
            <HeatmapGrid />
          </div>
        </div>

        <div className="divider" />

        {/* ── Section 2: AI Insights ── */}
        <InsightsSection
          insights={insights}
          onRefresh={async () => {
            const fresh = await api.refreshInsights();
            setInsights(fresh);
          }}
        />

        <div className="divider" />

        {/* ── Section 3: Daily Summary ── */}
        <DailySummary
          summary={summary}
          onGenerate={async () => {
            const r = await api.generateSummary();
            setSummary({ summary: r.summary, generated_at: new Date().toISOString() });
          }}
        />

        <div className="divider" />

        {/* ── Section 4: Chat ── */}
        <ChatInterface />
      </main>
    </div>
  );
}
