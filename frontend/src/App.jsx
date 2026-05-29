import { useEffect, useState, useCallback } from "react";
import { api } from "./api";
import Onboarding        from "./components/Onboarding";
import CalibrationWizard from "./components/CalibrationWizard";
import StoreStatusBar    from "./components/StoreStatusBar";
import CameraStatus      from "./components/CameraStatus";
import PinGate           from "./components/PinGate";
import AdminPage         from "./components/AdminPage";
import LiveWidget        from "./components/LiveWidget";
import LiveFeed          from "./components/LiveFeed";
import TodayStats        from "./components/TodayStats";
import HeatmapGrid       from "./components/HeatmapGrid";
import TrafficChart      from "./components/TrafficChart";
import InsightsSection   from "./components/InsightsSection";
import DailySummary      from "./components/DailySummary";
import ChatInterface     from "./components/ChatInterface";

const REFRESH_MS = 30_000;

export default function App() {
  // /admin route — no PIN needed (has its own password)
  if (window.location.pathname === "/admin") {
    return <AdminPage />;
  }

  return (
    <PinGate>
      <Dashboard />
    </PinGate>
  );
}

function Dashboard() {
  // 'loading' | 'connect' | 'setup' | 'dashboard'
  const [appState, setAppState] = useState("loading");

  useEffect(() => {
    // ?onboarding flag lets you preview/demo the onboarding flow at any time
    if (new URLSearchParams(window.location.search).get("onboarding") !== null) {
      setAppState("connect"); return;
    }
    const hasBackend = !!localStorage.getItem("iq_backend");
    const isDev = import.meta.env.DEV;
    api.setupStatus()
      .then(r => setAppState(r.setup_complete ? "dashboard" : "setup"))
      .catch(() => setAppState(isDev || hasBackend ? "dashboard" : "connect"));
  }, []);

  const [live,     setLive]     = useState(null);
  const [today,    setToday]    = useState(null);
  const [insights, setInsights] = useState(null);
  const [summary,  setSummary]  = useState(null);
  const [weather,  setWeather]  = useState(null);
  const [online,     setOnline]     = useState(false);
  const [store,      setStore]      = useState("RetailIQ");
  const [showCalib,  setShowCalib]  = useState(false);

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

  if (appState === "loading") return (
    <div className="ob-shell">
      <div className="ob-card" style={{ alignItems: "center" }}>
        <div className="ob-logo"><span>Retail</span>IQ</div>
        <p style={{ color: "var(--muted)", fontSize: "0.78rem" }}>Connecting…</p>
      </div>
    </div>
  );

  if (appState === "connect") return (
    <Onboarding startAtConnect={true} onComplete={() => setAppState("dashboard")} />
  );

  if (appState === "setup") return (
    <Onboarding startAtConnect={false} onComplete={() => setAppState("dashboard")} />
  );

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
          <button className="calib-trigger-btn" onClick={() => setShowCalib(true)} title="Setup & Calibration">
            ⚙ Calibrate
          </button>
        </div>
      </header>

      {showCalib && <CalibrationWizard onClose={() => setShowCalib(false)} />}

      <StoreStatusBar />

      <main className="content">
        {/* ── Section 1: Raw Data ── */}
        <div className="section">
          <div className="section-header">
            <div className="section-title">Section 1 — Live &amp; Raw Data</div>
          </div>

          <CameraStatus />
          <LiveFeed />
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
