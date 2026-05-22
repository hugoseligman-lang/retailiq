import { useEffect, useState, useCallback } from "react";
import { supabase } from "./supabase";
import HourlyChart   from "./components/HourlyChart";
import ZoneHeatmap   from "./components/ZoneHeatmap";
import ActivityFeed  from "./components/ActivityFeed";
import TrendCard     from "./components/TrendCard";
import OccupancyCard from "./components/OccupancyCard";

const SLOW_MS = 30_000;

function fmt(n) { return n == null ? "—" : String(n); }

export default function App() {
  const [live,     setLive]     = useState({ people_count: 0, created_at: null });
  const [prev,     setPrev]     = useState(null);   // second-latest reading for trend
  const [hourly,   setHourly]   = useState([]);
  const [zones,    setZones]    = useState(null);
  const [stats,    setStats]    = useState(null);
  const [feed,     setFeed]     = useState([]);
  const [online,   setOnline]   = useState(false);

  const fetchLive = useCallback(async () => {
    const { data, error } = await supabase
      .from("detections")
      .select("people_count, created_at, zone_left, zone_center, zone_right")
      .order("created_at", { ascending: false })
      .limit(2);
    if (!error && data?.length) {
      setLive(data[0]);
      if (data[1]) setPrev(data[1]);
      setOnline(true);
    } else { setOnline(false); }
  }, []);

  const fetchSlow = useCallback(async () => {
    const [h, z, s, f] = await Promise.all([
      supabase.from("hourly_today").select("*"),
      supabase.from("zone_totals_today").select("*").single(),
      supabase.from("stats_today").select("*").single(),
      supabase.from("detections")
        .select("people_count, created_at, zone_left, zone_center, zone_right")
        .order("created_at", { ascending: false })
        .limit(12),
    ]);
    if (!h.error) setHourly(h.data ?? []);
    if (!z.error) setZones(z.data);
    if (!s.error) setStats(s.data);
    if (!f.error) setFeed(f.data ?? []);
  }, []);

  useEffect(() => {
    fetchLive();
    fetchSlow();

    const channel = supabase
      .channel("detections-live")
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "detections" },
        (payload) => {
          setPrev(live);
          setLive(payload.new);
          setOnline(true);
          setFeed(prev => [payload.new, ...prev].slice(0, 12));
        })
      .subscribe();

    const t = setInterval(fetchSlow, SLOW_MS);
    return () => { supabase.removeChannel(channel); clearInterval(t); };
  }, [fetchLive, fetchSlow]);

  // Derived numbers
  const totalZone  = (zones?.total_left ?? 0) + (zones?.total_center ?? 0) + (zones?.total_right ?? 0);
  const avgHourly  = hourly.length
    ? Math.round(hourly.reduce((s, h) => s + Number(h.avg_count), 0) / hourly.length * 10) / 10
    : 0;

  const trend = prev != null
    ? live.people_count - prev.people_count
    : 0;

  const today = new Date().toLocaleDateString("en-AU", { weekday:"long", day:"numeric", month:"long", year:"numeric" });

  return (
    <div className="dashboard">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-left">
          <div className="logo"><span>Retail</span>IQ</div>
          <div className="header-date">{today}</div>
        </div>
        <div className="header-right">
          <div className={`status-badge ${online ? "live" : ""}`}>
            <span className="status-dot" />
            {online ? "Live" : "Connecting…"}
          </div>
        </div>
      </header>

      {/* ── Top metric strip ── */}
      <div className="metrics-strip">
        <div className="metric-card highlight">
          <div className="metric-label">Live Count</div>
          <div className="metric-value">{live.people_count}</div>
          <div className="metric-change">
            {trend > 0 ? `▲ +${trend} since last scan` : trend < 0 ? `▼ ${trend} since last scan` : "No change"}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Total Detections</div>
          <div className="metric-value">{fmt(stats?.total_detections)}</div>
          <div className="metric-change">Today</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Peak Count</div>
          <div className="metric-value">{fmt(stats?.peak_count)}</div>
          <div className="metric-change">Highest reading today</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Peak Hour</div>
          <div className="metric-value" style={{fontSize:"1.4rem"}}>{stats?.peak_hour ?? "—"}</div>
          <div className="metric-change">Busiest hour today</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Avg Occupancy</div>
          <div className="metric-value">{avgHourly}</div>
          <div className="metric-change">Per hour average</div>
        </div>
      </div>

      {/* ── Main grid ── */}
      <div className="main-grid">
        <HourlyChart hourly={hourly} />
        <div className="right-col">
          <ZoneHeatmap zones={zones} totalZone={totalZone} />
          <ActivityFeed feed={feed} />
        </div>
      </div>

      {/* ── Bottom strip ── */}
      <div className="bottom-strip">
        <TrendCard live={live} prev={prev} trend={trend} />
        <OccupancyCard live={live} stats={stats} />
        <div className="card">
          <div className="card-title">Zone Split — Today</div>
          {["Left","Centre","Right"].map((z, i) => {
            const key = ["total_left","total_center","total_right"][i];
            const val = zones?.[key] ?? 0;
            const pct = totalZone ? Math.round(val / totalZone * 100) : 0;
            return (
              <div key={z} style={{marginBottom:10}}>
                <div style={{display:"flex",justifyContent:"space-between",fontSize:"0.75rem",fontWeight:600,marginBottom:4}}>
                  <span>{z}</span><span>{pct}%</span>
                </div>
                <div className="occ-bar-track">
                  <div className="occ-bar-fill" style={{width:`${pct}%`, background: i===0?"#FBBF24":i===1?"#F59E0B":"#F97316"}} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
