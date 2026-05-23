import { useState } from "react";
import { api } from "../api";

function renderMarkdown(text) {
  // Minimal bold rendering for **text** and *text*
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

export default function DailySummary({ summary, onGenerate }) {
  const [loading, setLoading] = useState(false);

  async function handleGenerate() {
    setLoading(true);
    try { await onGenerate(); } finally { setLoading(false); }
  }

  const text = summary?.summary || "";
  const ts   = summary?.generated_at
    ? new Date(summary.generated_at).toLocaleString("en-AU")
    : null;

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Section 3 — Daily AI Summary</div>
        <button className="generate-btn" onClick={handleGenerate} disabled={loading}>
          {loading ? "Generating…" : "Generate Now"}
        </button>
      </div>
      <div className="card">
        {!text ? (
          <div className="insights-empty">
            No summary yet — auto-generates at your configured day-end time, or click Generate Now.
          </div>
        ) : (
          <>
            <div
              className="summary-card"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }}
            />
            {ts && <div className="summary-meta">Generated {ts}</div>}
          </>
        )}
      </div>
    </div>
  );
}
