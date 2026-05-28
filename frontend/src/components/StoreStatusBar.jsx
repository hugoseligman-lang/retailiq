import { useEffect, useState, useCallback } from "react";
import { api } from "../api";

export default function StoreStatusBar() {
  const [status,    setStatus]    = useState(null);   // "open" | "closed" | null
  const [openedAt,  setOpenedAt]  = useState(null);
  const [closedAt,  setClosedAt]  = useState(null);
  const [loading,   setLoading]   = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.storeStatus();
      setStatus(s.status);
      setOpenedAt(s.opened_at || null);
      setClosedAt(s.closed_at || null);
    } catch {
      // backend not reachable — leave as null
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 30_000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  async function toggle() {
    if (loading) return;
    setLoading(true);
    try {
      if (status === "open") {
        await api.storeClose();
      } else {
        await api.storeOpen();
      }
      await fetchStatus();
    } catch (e) {
      console.error("store toggle error", e);
    } finally {
      setLoading(false);
    }
  }

  function fmt(iso) {
    if (!iso) return null;
    try {
      return new Date(iso).toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit" });
    } catch {
      return null;
    }
  }

  const isOpen   = status === "open";
  const isUnknown = status === null;

  let subtext = null;
  if (isOpen && openedAt)   subtext = `Opened at ${fmt(openedAt)}`;
  if (!isOpen && !isUnknown && closedAt) subtext = `Closed at ${fmt(closedAt)}`;

  return (
    <div className={`store-status-bar ${isOpen ? "store-open" : isUnknown ? "store-unknown" : "store-closed"}`}>
      <div className="store-status-left">
        <span className="store-status-dot" />
        <span className="store-status-label">
          {isUnknown ? "Store" : isOpen ? "Open for Business" : "Store Closed"}
        </span>
        {subtext && <span className="store-status-sub">{subtext}</span>}
      </div>
      <button
        className={`store-status-btn ${isOpen ? "store-btn-close" : "store-btn-open"}`}
        onClick={toggle}
        disabled={loading || isUnknown}
      >
        {loading ? "…" : isOpen ? "Close for the Day" : "Open for Business"}
      </button>
    </div>
  );
}
