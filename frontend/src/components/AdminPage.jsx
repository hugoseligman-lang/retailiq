/**
 * AdminPage — password-protected admin panel.
 * Rendered when the URL path is /admin.
 * Password is sent as X-Admin-Password header on every request.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../api";

const PW_KEY = "iq_admin_pw";

export default function AdminPage() {
  const [authed,   setAuthed]   = useState(false);
  const [password, setPassword] = useState("");
  const [pwError,  setPwError]  = useState(false);
  const [status,   setStatus]   = useState(null);
  const [camMode,  setCamMode]  = useState("");
  const [camSrc,   setCamSrc]   = useState("");
  const [saving,   setSaving]   = useState(false);
  const [msg,      setMsg]      = useState("");
  const pollRef = useRef(null);

  // Restore saved password
  useEffect(() => {
    const saved = sessionStorage.getItem(PW_KEY);
    if (saved) tryLogin(saved);
  }, []);

  async function tryLogin(pw) {
    try {
      const s = await api.adminStatus(pw);
      if (s.error) { setPwError(true); return; }
      sessionStorage.setItem(PW_KEY, pw);
      setAuthed(true);
      setStatus(s);
      setCamMode(s.camera_mode || "");
    } catch {
      setPwError(true);
    }
  }

  const fetchStatus = useCallback(async () => {
    const pw = sessionStorage.getItem(PW_KEY);
    if (!pw) return;
    try {
      const s = await api.adminStatus(pw);
      setStatus(s);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (!authed) return;
    pollRef.current = setInterval(fetchStatus, 5000);
    return () => clearInterval(pollRef.current);
  }, [authed, fetchStatus]);

  // Load camera config once after login
  useEffect(() => {
    if (!authed) return;
    const pw = sessionStorage.getItem(PW_KEY);
    api.adminGetCamera(pw).then(r => {
      setCamMode(r.camera_mode || "");
      setCamSrc(r.camera_source || "");
    }).catch(() => {});
  }, [authed]);

  async function doAction(fn, label) {
    setMsg("");
    try {
      await fn();
      setMsg(`${label} — done`);
      fetchStatus();
    } catch (e) {
      setMsg(`Error: ${e.message}`);
    }
  }

  async function saveCameraConfig() {
    setSaving(true);
    setMsg("");
    const pw = sessionStorage.getItem(PW_KEY);
    try {
      await api.adminSetCamera(pw, camMode, camSrc);
      setMsg("Camera updated — server restarting…");
    } catch (e) {
      setMsg(`Error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  }

  function logout() {
    sessionStorage.removeItem(PW_KEY);
    setAuthed(false);
    setPassword("");
    setStatus(null);
  }

  // ── Login screen ───────────────────────────────────────────────────────
  if (!authed) {
    return (
      <div className="pin-shell">
        <div className="pin-card">
          <div className="pin-logo"><span>Retail</span>IQ</div>
          <p className="pin-title">Admin Access</p>
          <input
            className="admin-pw-input"
            type="password"
            placeholder="Admin password"
            value={password}
            onChange={e => { setPassword(e.target.value); setPwError(false); }}
            onKeyDown={e => e.key === "Enter" && tryLogin(password)}
            autoFocus
          />
          {pwError && <p className="pin-error">Incorrect password</p>}
          <button
            className="pin-submit"
            onClick={() => tryLogin(password)}
            disabled={!password}
          >
            Sign in
          </button>
        </div>
      </div>
    );
  }

  // ── Admin dashboard ────────────────────────────────────────────────────
  const pw = sessionStorage.getItem(PW_KEY) || "";

  function StatusDot({ ok }) {
    return (
      <span
        style={{
          display: "inline-block", width: 10, height: 10, borderRadius: "50%",
          background: ok ? "var(--green)" : "var(--red)",
          boxShadow: ok ? "0 0 6px var(--green)" : "none",
          marginRight: 8, verticalAlign: "middle",
        }}
      />
    );
  }

  const frameAge = status?.frame_age_seconds;
  const cameraOk = status?.frame_fresh ?? (frameAge !== null && frameAge !== undefined && frameAge < 30);

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-logo"><span>Retail</span>IQ <span style={{ color: "var(--muted)", fontSize: "0.7rem", fontWeight: 400 }}>Admin</span></div>
        <div className="topbar-meta">
          <a href="/" style={{ color: "var(--muted)", fontSize: "0.72rem", textDecoration: "none" }}>← Dashboard</a>
          <button
            onClick={logout}
            style={{ background: "none", border: "1px solid var(--border)", borderRadius: 6,
                     color: "var(--muted)", fontSize: "0.72rem", padding: "3px 12px", cursor: "pointer" }}
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="content" style={{ maxWidth: 760 }}>

        {/* ── System Status ── */}
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="card-label">System Status</div>
          {status ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
              <StatusRow label="Camera feed">
                <StatusDot ok={cameraOk} />
                {cameraOk
                  ? `Connected — last frame ${frameAge !== null ? `${frameAge}s ago` : "just now"}`
                  : `No frames — ${frameAge !== null ? `last seen ${frameAge}s ago` : "never received"}`}
              </StatusRow>
              <StatusRow label="Camera mode">
                <code style={{ fontSize: "0.78rem", color: "var(--amber)" }}>{status.camera_mode || "—"}</code>
              </StatusRow>
              <StatusRow label="HOG tracker">
                <StatusDot ok={status.tracker_running} />
                {status.tracker_running ? "Running" : "Stopped"}
              </StatusRow>
              <StatusRow label="Counting">
                <StatusDot ok={status.counting_active} />
                {status.counting_active ? "Active" : "Paused"}
              </StatusRow>
              <StatusRow label="In store now">{status.in_store ?? "—"}</StatusRow>
              <StatusRow label="Entries today">{status.entries_today ?? "—"}</StatusRow>
              <StatusRow label="Server time">
                <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>{status.server_time || "—"}</span>
              </StatusRow>
            </div>
          ) : (
            <p style={{ color: "var(--muted)", fontSize: "0.78rem", marginTop: 12 }}>Loading…</p>
          )}
        </div>

        {/* ── Controls ── */}
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="card-label">Controls</div>
          <div style={{ display: "flex", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
            <AdminBtn
              label="Pause counting"
              colour="var(--amber)"
              disabled={!status?.counting_active}
              onClick={() => doAction(() => api.adminPause(pw), "Counting paused")}
            />
            <AdminBtn
              label="Resume counting"
              colour="var(--green)"
              disabled={status?.counting_active}
              onClick={() => doAction(() => api.adminResume(pw), "Counting resumed")}
            />
            <AdminBtn
              label="Restart server"
              colour="var(--red)"
              onClick={() => {
                if (window.confirm("Restart the RetailIQ server process? It will be back in ~5 seconds.")) {
                  doAction(() => api.adminRestart(pw), "Restarting…");
                }
              }}
            />
          </div>
          {msg && (
            <p style={{ marginTop: 12, fontSize: "0.76rem", color: "var(--green)" }}>{msg}</p>
          )}
        </div>

        {/* ── Camera Configuration ── */}
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="card-label">Camera Configuration</div>
          <p style={{ fontSize: "0.72rem", color: "var(--muted)", margin: "10px 0 16px" }}>
            Changing these settings will write to <code>.env</code> and restart the server.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <label style={{ fontSize: "0.72rem", color: "var(--muted)" }}>
              Camera mode
              <select
                value={camMode}
                onChange={e => setCamMode(e.target.value)}
                style={{
                  display: "block", marginTop: 6, width: "100%",
                  background: "var(--surface2)", border: "1px solid var(--border)",
                  borderRadius: 8, padding: "8px 12px", color: "var(--text)", fontSize: "0.8rem",
                }}
              >
                <option value="webcam">webcam — USB camera on this server</option>
                <option value="rtsp">rtsp — IP/CCTV camera via RTSP URL</option>
                <option value="http">http — HTTP MJPEG/snapshot stream</option>
                <option value="vps">vps — frames pushed by camera_bridge.py</option>
              </select>
            </label>

            {camMode !== "vps" && (
              <label style={{ fontSize: "0.72rem", color: "var(--muted)" }}>
                Camera source / URL
                <input
                  type="text"
                  value={camSrc}
                  onChange={e => setCamSrc(e.target.value)}
                  placeholder={camMode === "rtsp" ? "rtsp://user:pass@192.168.1.100:554/stream" : "0"}
                  style={{
                    display: "block", marginTop: 6, width: "100%",
                    background: "var(--surface2)", border: "1px solid var(--border)",
                    borderRadius: 8, padding: "8px 12px", color: "var(--text)", fontSize: "0.8rem",
                    fontFamily: "monospace",
                  }}
                />
              </label>
            )}

            <button
              className="generate-btn"
              onClick={saveCameraConfig}
              disabled={saving}
              style={{ alignSelf: "flex-start" }}
            >
              {saving ? "Saving…" : "Save & Restart"}
            </button>
          </div>
        </div>

        {/* ── SSH quick-reference ── */}
        <div className="card">
          <div className="card-label">SSH Quick Reference</div>
          <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
            <CodeLine label="View logs"        cmd="journalctl -fu retailiq" />
            <CodeLine label="Restart service"  cmd="systemctl restart retailiq" />
            <CodeLine label="Edit config"      cmd="nano /opt/retailiq/backend/.env" />
            <CodeLine label="Update code"      cmd="bash /opt/retailiq/update_vps.sh" />
          </div>
        </div>

      </main>
    </div>
  );
}


function StatusRow({ label, children }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: "0.78rem" }}>
      <span style={{ color: "var(--muted)", minWidth: 120 }}>{label}</span>
      <span style={{ color: "var(--text)" }}>{children}</span>
    </div>
  );
}

function AdminBtn({ label, colour, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: "8px 18px", borderRadius: 8, border: `1px solid ${colour}`,
        background: "transparent", color: disabled ? "var(--muted)" : colour,
        borderColor: disabled ? "var(--border)" : colour,
        fontSize: "0.76rem", fontWeight: 700, cursor: disabled ? "not-allowed" : "pointer",
        transition: "all .15s",
      }}
    >
      {label}
    </button>
  );
}

function CodeLine({ label, cmd }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(cmd).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ fontSize: "0.68rem", color: "var(--muted)", minWidth: 110 }}>{label}</span>
      <code
        style={{
          flex: 1, background: "var(--surface2)", border: "1px solid var(--border)",
          borderRadius: 6, padding: "5px 10px", fontSize: "0.72rem", color: "var(--amber)",
          cursor: "pointer",
        }}
        onClick={copy}
        title="Click to copy"
      >
        {cmd}
      </code>
      {copied && <span style={{ fontSize: "0.66rem", color: "var(--green)" }}>Copied</span>}
    </div>
  );
}
