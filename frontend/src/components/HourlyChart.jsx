import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
} from "chart.js";
import { Bar } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip);

// Fill in all 24 hours even if Supabase only returns hours with data
function buildFull(rows) {
  const map = Object.fromEntries((rows ?? []).map((r) => [r.hour, r]));
  return Array.from({ length: 24 }, (_, i) => {
    const h = String(i).padStart(2, "0");
    return map[h] ?? { hour: h, peak_count: 0, avg_count: 0 };
  });
}

export default function HourlyChart({ hourly }) {
  const full   = buildFull(hourly);
  const labels = full.map((h) => `${h.hour}:00`);
  const data   = full.map((h) => h.peak_count);

  const chartData = {
    labels,
    datasets: [
      {
        label: "Peak Count",
        data,
        backgroundColor: (ctx) => {
          const grad = ctx.chart.ctx.createLinearGradient(0, 0, 0, 200);
          grad.addColorStop(0, "rgba(99,102,241,0.85)");
          grad.addColorStop(1, "rgba(99,102,241,0.15)");
          return grad;
        },
        borderRadius: 6,
        borderSkipped: false,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { mode: "index" } },
    scales: {
      x: {
        grid: { color: "#1e2540" },
        ticks: { color: "#64748b", font: { size: 11 }, maxTicksLimit: 12 },
      },
      y: {
        grid: { color: "#1e2540" },
        ticks: { color: "#64748b", font: { size: 11 }, stepSize: 1 },
        beginAtZero: true,
      },
    },
  };

  return (
    <div className="card" style={{ height: 260 }}>
      <div className="card-title">Hourly Traffic — Today</div>
      <div style={{ height: 200 }}>
        <Bar data={chartData} options={options} />
      </div>
    </div>
  );
}
