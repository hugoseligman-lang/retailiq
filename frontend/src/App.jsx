import { useEffect, useState, useCallback } from "react";
import { supabase } from "./supabase";
import LiveCount   from "./components/LiveCount";
import HourlyChart from "./components/HourlyChart";
import ZoneHeatmap from "./components/ZoneHeatmap";
import StatsPanel  from "./components/StatsPanel";

const SLOW_REFRESH_MS = 30_000; // hourly / zone / stats refresh rate

export default function App() {
  const [live,   setLive]   = useState({ people_count: 0, created_at: null });
  const [hourly, setHourly] = useState([]);
  const [zones,  setZones]  = useState(null);
  const [stats,  setStats]  = useState(null);
  const [online, setOnline] = useState(false);

  // ── slow data (aggregates) ──────────────────────────────────
  const fetchSlow = useCallback(async () => {
    const [h, z, s] = await Promise.all([
      supabase.from("hourly_today").select("*"),
      supabase.from("zone_totals_today").select("*").single(),
      supabase.from("stats_today").select("*").single(),
    ]);
    if (!h.error) setHourly(h.data ?? []);
    if (!z.error) setZones(z.data);
    if (!s.error) setStats(s.data);
  }, []);

  // ── live count: initial fetch ───────────────────────────────
  const fetchLive = useCallback(async () => {
    const { data, error } = await supabase
      .from("detections")
      .select("people_count, created_at")
      .order("created_at", { ascending: false })
      .limit(1)
      .single();
    if (!error && data) {
      setLive(data);
      setOnline(true);
    } else {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    // initial loads
    fetchLive();
    fetchSlow();

    // real-time subscription for live count
    const channel = supabase
      .channel("detections-live")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "detections" },
        (payload) => {
          setLive(payload.new);
          setOnline(true);
        }
      )
      .subscribe();

    // slow refresh for aggregates
    const slowTimer = setInterval(fetchSlow, SLOW_REFRESH_MS);

    return () => {
      supabase.removeChannel(channel);
      clearInterval(slowTimer);
    };
  }, [fetchLive, fetchSlow]);

  return (
    <div className="dashboard">
      <header className="header">
        <h1><span>Retail</span>IQ</h1>
        <span className="status-label">
          <span className={`status-dot ${online ? "" : "offline"}`} />
          {online ? "Live" : "Connecting…"}
        </span>
      </header>

      <div className="grid-top">
        <LiveCount count={live.people_count} lastUpdated={live.created_at} online={online} />
        <StatsPanel stats={stats} />
        <ZoneHeatmap zones={zones} />
      </div>

      <div className="grid-bottom">
        <HourlyChart hourly={hourly} />
      </div>
    </div>
  );
}
