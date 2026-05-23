import { useState, useEffect } from "react";
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  LineElement, PointElement, Tooltip, Legend, Filler,
} from "chart.js";
import { Bar } from "react-chartjs-2";
import { api } from "../api";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Tooltip, Legend, Filler);

const WMO_ICON = {
  0:"☀️", 1:"🌤️", 2:"⛅", 3:"☁️", 45:"🌫️", 48:"🌫️",
  51:"🌦️", 53:"🌦️", 55:"🌧️", 61:"🌧️", 63:"🌧️", 65:"🌧️",
  80:"🌦️", 81:"🌧️", 82:"⛈️", 95:"⛈️",
};

function weatherIcon(code) { return WMO_ICON[code] ?? "🌡️"; }

export default function TrafficChart() {
  const [overlay, setOverlay]  = useState("none");
  const [data, setData]        = useState(null);

  useEffect(() => {
    api.traffic(overlay).then(setData).catch(() => {});
  }, [overlay]);

  const today = data?.today ?? [];
  const over  = data?.overlay ?? [];

  const labels = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2,"0")}:00`);
  const todayVals  = labels.map((_, i) => {
    const h = today.find(r => String(r.hour).padStart(2,"0") === String(i).padStart(2,"0"));
    return h ? Number(h.avg_count || 0) : 0;
  });
  const overlayVals = over.length ? labels.map((_, i) => {
    const h = over.find(r => Number(r.hour) === i);
    return h ? Number(h.avg_people || h.avg_count || 0) : 0;
  }) : [];

  // Weather icons from today's hourly data
  const plugins_weather = {
    id: "weatherIcons",
    afterDraw(chart) {
      if (!today.length) return;
      const { ctx, chartArea: { top }, scales: { x } } = chart;
      today.forEach(h => {
        if (!h.weather_code) return;
        const idx  = Number(h.hour);
        const xPos = x.getPixelForValue(idx);
        ctx.font = "11px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(weatherIcon(h.weather_code), xPos, top - 4);
      });
    },
  };

  const chartData = {
    labels,
    datasets: [
      {
        type: "bar",
        label: "Today",
        data: todayVals,
        backgroundColor: "rgba(245,158,11,0.7)",
        borderRadius: 5,
        borderSkipped: false,
        order: 2,
      },
      ...(overlayVals.length ? [{
        type: "line",
        label: data?.overlay_label ?? "Overlay",
        data: overlayVals,
        borderColor: "rgba(99,102,241,0.9)",
        backgroundColor: "rgba(99,102,241,0.08)",
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.35,
        fill: true,
        order: 1,
      }] : []),
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: "#8B949E", font: { size: 11 } } },
      tooltip: {
        backgroundColor: "#21262D",
        titleColor: "#E6EDF3",
        bodyColor: "#8B949E",
        borderColor: "#30363D",
        borderWidth: 1,
        padding: 10,
      },
    },
    scales: {
      x: { grid: { color: "#21262D" }, ticks: { color: "#8B949E", font: { size: 10 }, maxTicksLimit: 12 } },
      y: { grid: { color: "#21262D" }, ticks: { color: "#8B949E", font: { size: 10 } }, beginAtZero: true },
    },
    layout: { padding: { top: 18 } },
  };

  const overlays = [
    { key: "none",       label: "Today Only" },
    { key: "yesterday",  label: "vs Yesterday" },
    { key: "last_week",  label: "vs Last Week" },
    { key: "last_month", label: "vs Last Month" },
  ];

  return (
    <div className="card chart-card">
      <div className="section-header" style={{ marginBottom: 4 }}>
        <div className="card-label" style={{ marginBottom: 0 }}>Hourly Traffic</div>
        <div className="chart-controls">
          {overlays.map(o => (
            <button key={o.key} className={`toggle-btn ${overlay === o.key ? "active" : ""}`}
              onClick={() => setOverlay(o.key)}>
              {o.label}
            </button>
          ))}
        </div>
      </div>
      <div className="chart-inner">
        <Bar data={chartData} options={options} plugins={[plugins_weather]} />
      </div>
    </div>
  );
}
