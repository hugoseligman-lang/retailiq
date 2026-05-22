import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  LineElement, PointElement, Tooltip, Filler,
} from "chart.js";
import { Bar } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Tooltip, Filler);

function buildFull(rows) {
  const map = Object.fromEntries((rows ?? []).map(r => [r.hour, r]));
  return Array.from({ length: 24 }, (_, i) => {
    const h = String(i).padStart(2, "0");
    return map[h] ?? { hour: h, peak_count: 0, avg_count: 0 };
  });
}

export default function HourlyChart({ hourly }) {
  const full   = buildFull(hourly);
  const labels = full.map(h => `${h.hour}:00`);
  const peaks  = full.map(h => h.peak_count);
  const avgs   = full.map(h => Number(h.avg_count));

  const chartData = {
    labels,
    datasets: [
      {
        type: "bar",
        label: "Peak",
        data: peaks,
        backgroundColor: ctx => {
          const grad = ctx.chart.ctx.createLinearGradient(0, 0, 0, 180);
          grad.addColorStop(0, "rgba(251,191,36,0.9)");
          grad.addColorStop(1, "rgba(245,158,11,0.3)");
          return grad;
        },
        borderRadius: 6,
        borderSkipped: false,
        order: 2,
      },
      {
        type: "line",
        label: "Avg",
        data: avgs,
        borderColor: "#F97316",
        backgroundColor: "transparent",
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.4,
        order: 1,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#fff",
        titleColor: "#292524",
        bodyColor: "#78716C",
        borderColor: "#FDE68A",
        borderWidth: 1,
        padding: 10,
      },
    },
    scales: {
      x: {
        grid: { color: "#FEF3C7" },
        ticks: { color: "#A8A29E", font: { size: 10 }, maxTicksLimit: 12 },
      },
      y: {
        grid: { color: "#FEF3C7" },
        ticks: { color: "#A8A29E", font: { size: 10 }, stepSize: 1 },
        beginAtZero: true,
      },
    },
  };

  return (
    <div className="card chart-card">
      <div className="card-title">Hourly Traffic — Today <span style={{float:"right",color:"#F97316",fontWeight:700,fontSize:"0.65rem"}}>— Avg &nbsp; ▌ Peak</span></div>
      <div className="chart-inner">
        <Bar data={chartData} options={options} />
      </div>
    </div>
  );
}
