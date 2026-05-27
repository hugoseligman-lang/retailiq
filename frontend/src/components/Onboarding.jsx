import { useState, useRef } from "react";
import { api, setBackend } from "../api";

const STATE_TZ = {
  NSW: "Australia/Sydney",
  VIC: "Australia/Melbourne",
  QLD: "Australia/Brisbane",
  WA:  "Australia/Perth",
  SA:  "Australia/Adelaide",
  TAS: "Australia/Hobart",
  ACT: "Australia/Sydney",
  NT:  "Australia/Darwin",
};

const ADMIN1_STATE = {
  "New South Wales":              "NSW",
  "Victoria":                     "VIC",
  "Queensland":                   "QLD",
  "Western Australia":            "WA",
  "South Australia":              "SA",
  "Tasmania":                     "TAS",
  "Australian Capital Territory": "ACT",
  "Northern Territory":           "NT",
};

const CAMERA_MODES = [
  { id: "webcam", label: "USB Webcam", icon: "📷", desc: "Built-in or USB camera" },
  { id: "rtsp",   label: "IP Camera",  icon: "📡", desc: "RTSP network stream" },
  { id: "http",   label: "Web Stream", icon: "🌐", desc: "HTTP stream or snapshot" },
  { id: "arlo",   label: "Arlo",       icon: "🔒", desc: "Arlo wireless camera" },
];

const PROGRESS_STEPS = ["store", "location", "camera", "schedule"];

export default function Onboarding({ startAtConnect, onComplete }) {
  const [step, setStep] = useState(startAtConnect ? "connect" : "welcome");
  const [form, setFormState] = useState({
    backend_url:      "http://localhost:5050",
    store_name:       "",
    state:            "NSW",
    timezone:         "Australia/Sydney",
    lat:              "",
    lon:              "",
    location_display: "",
    camera_mode:      "webcam",
    camera_source:    "0",
    arlo_email:       "",
    arlo_password:    "",
    arlo_device:      "",
    day_end_time:     "18:00",
    capture_interval: "3",
    queue_threshold:  "2",
  });

  const [locationQuery,   setLocationQuery]   = useState("");
  const [locationResults, setLocationResults] = useState([]);
  const [locationLoading, setLocationLoading] = useState(false);
  const [connectLoading,  setConnectLoading]  = useState(false);
  const [connectError,    setConnectError]    = useState("");
  const [submitting,      setSubmitting]      = useState(false);
  const [submitError,     setSubmitError]     = useState("");
  const [done,            setDone]            = useState(false);
  const debounce = useRef(null);

  function set(key, val) {
    setFormState(f => ({ ...f, [key]: val }));
  }

  const ORDER = startAtConnect
    ? ["connect", "welcome", "store", "location", "camera", "schedule"]
    : ["welcome", "store", "location", "camera", "schedule"];

  function advance() {
    const idx = ORDER.indexOf(step);
    if (idx < ORDER.length - 1) setStep(ORDER[idx + 1]);
  }

  function goBack() {
    const idx = ORDER.indexOf(step);
    if (idx > 0) setStep(ORDER[idx - 1]);
  }

  // ── Backend connection ─────────────────────────────────────────────────────

  async function testAndConnect() {
    setConnectLoading(true);
    setConnectError("");
    try {
      const healthUrl = form.backend_url.replace(/\/+$/, "") + "/api/health";
      const r = await fetch(healthUrl, { cache: "no-cache" });
      if (!r.ok) throw new Error("bad status");
      setBackend(form.backend_url);
      const status = await api.setupStatus();
      if (status.setup_complete) { onComplete(); return; }
      setStep("welcome");
    } catch {
      setConnectError(
        "Could not reach the backend. Make sure it is running on this computer (python main.py) and try again."
      );
    } finally {
      setConnectLoading(false);
    }
  }

  // ── Location geocode ───────────────────────────────────────────────────────

  function handleLocationInput(q) {
    setLocationQuery(q);
    setLocationResults([]);
    clearTimeout(debounce.current);
    if (!q.trim()) return;
    debounce.current = setTimeout(async () => {
      setLocationLoading(true);
      try {
        const data = await api.geocode(q);
        setLocationResults(
          (data.results || []).filter(r => r.country_code === "AU").slice(0, 6)
        );
      } catch {}
      finally { setLocationLoading(false); }
    }, 400);
  }

  function pickLocation(r) {
    const stateCode = ADMIN1_STATE[r.admin1] || "NSW";
    setFormState(f => ({
      ...f,
      lat:              String(r.latitude),
      lon:              String(r.longitude),
      location_display: `${r.name}, ${r.admin1}`,
      state:            stateCode,
      timezone:         STATE_TZ[stateCode] || "Australia/Sydney",
    }));
    setLocationQuery(`${r.name}, ${r.admin1}`);
    setLocationResults([]);
  }

  // ── Submit ─────────────────────────────────────────────────────────────────

  async function submit() {
    setSubmitting(true);
    setSubmitError("");
    try {
      await api.submitSetup({
        store_name:       form.store_name,
        state:            form.state,
        timezone:         form.timezone,
        lat:              form.lat,
        lon:              form.lon,
        camera_mode:      form.camera_mode,
        camera_source:    form.camera_mode === "arlo" ? form.arlo_device : form.camera_source,
        arlo_email:       form.arlo_email,
        arlo_password:    form.arlo_password,
        arlo_device:      form.arlo_device,
        day_end_time:     form.day_end_time,
        capture_interval: form.capture_interval,
        queue_threshold:  form.queue_threshold,
      });
      setDone(true);
    } catch {
      setSubmitError("Could not save settings — check the backend is still running.");
    } finally {
      setSubmitting(false);
    }
  }

  // ── Validation ─────────────────────────────────────────────────────────────

  function canAdvance() {
    if (step === "store")    return form.store_name.trim().length > 0;
    if (step === "location") return !!form.lat && !!form.lon;
    if (step === "camera") {
      if (form.camera_mode === "arlo")    return !!(form.arlo_email && form.arlo_password && form.arlo_device);
      if (form.camera_mode !== "webcam")  return form.camera_source.trim().length > 0;
    }
    return true;
  }

  const progressIdx = PROGRESS_STEPS.indexOf(step);

  // ── Done ───────────────────────────────────────────────────────────────────

  if (done) return (
    <div className="ob-shell">
      <div className="ob-card">
        <div className="ob-logo"><span>Retail</span>IQ</div>
        <div className="ob-done">
          <div className="ob-done-check">✓</div>
          <h2 className="ob-done-title">{form.store_name} is live</h2>
          <p className="ob-done-sub">
            Your dashboard is ready. Start the camera feed on the backend to begin tracking visitors.
          </p>
          <button className="ob-btn ob-primary ob-lg" onClick={onComplete}>
            Open Dashboard →
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="ob-shell">
      <div className="ob-card">
        <div className="ob-logo"><span>Retail</span>IQ</div>

        {progressIdx >= 0 && (
          <div className="ob-progress">
            {PROGRESS_STEPS.map((s, i) => (
              <div key={s} className={`ob-dot${i < progressIdx ? " ob-dot-done" : i === progressIdx ? " ob-dot-active" : ""}`} />
            ))}
          </div>
        )}

        {/* Connect Backend */}
        {step === "connect" && (
          <div className="ob-step">
            <div className="ob-hero-icon">🔌</div>
            <h2 className="ob-step-title">Connect Your Backend</h2>
            <p className="ob-step-sub">
              Open this page on the computer running the RetailIQ backend, then click Connect.
            </p>
            <div className="ob-field">
              <label>Backend URL</label>
              <input
                className="ob-input"
                value={form.backend_url}
                onChange={e => set("backend_url", e.target.value)}
                placeholder="http://localhost:5050"
                autoFocus
              />
              <span className="ob-hint">
                Default is http://localhost:5050. Change only if accessing over a local network.
              </span>
            </div>
            {connectError && <div className="ob-error">{connectError}</div>}
            <div className="ob-nav ob-nav-end">
              <button className="ob-btn ob-primary" onClick={testAndConnect} disabled={connectLoading}>
                {connectLoading ? "Connecting…" : "Connect →"}
              </button>
            </div>
          </div>
        )}

        {/* Welcome */}
        {step === "welcome" && (
          <div className="ob-step ob-welcome">
            <div className="ob-hero-icon">🏪</div>
            <h1 className="ob-welcome-title">Welcome to RetailIQ</h1>
            <p className="ob-welcome-sub">
              AI-powered retail analytics for your store.<br />
              Setup takes under 2 minutes.
            </p>
            <button className="ob-btn ob-primary ob-lg" onClick={advance}>
              Get Started →
            </button>
          </div>
        )}

        {/* Store */}
        {step === "store" && (
          <div className="ob-step">
            <h2 className="ob-step-title">Your Store</h2>
            <p className="ob-step-sub">Basic details about the store you're monitoring.</p>
            <div className="ob-field">
              <label>Store Name</label>
              <input
                className="ob-input"
                placeholder="e.g. Main Street Retail"
                value={form.store_name}
                onChange={e => set("store_name", e.target.value)}
                autoFocus
              />
            </div>
            <div className="ob-field">
              <label>State / Territory</label>
              <select className="ob-input" value={form.state} onChange={e => {
                set("state", e.target.value);
                set("timezone", STATE_TZ[e.target.value]);
              }}>
                {Object.keys(STATE_TZ).map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
        )}

        {/* Location */}
        {step === "location" && (
          <div className="ob-step">
            <h2 className="ob-step-title">Store Location</h2>
            <p className="ob-step-sub">Used for live weather and AI traffic context.</p>
            <div className="ob-field ob-field-loc">
              <label>Suburb or Postcode</label>
              <input
                className="ob-input"
                placeholder="e.g. Hornsby"
                value={locationQuery}
                onChange={e => handleLocationInput(e.target.value)}
                autoComplete="off"
                autoFocus
              />
              {locationLoading && <div className="ob-loc-spinner">Searching…</div>}
              {locationResults.length > 0 && (
                <div className="ob-loc-dropdown">
                  {locationResults.map(r => (
                    <button key={r.id} className="ob-loc-item" onClick={() => pickLocation(r)}>
                      <span className="ob-loc-name">{r.name}</span>
                      <span className="ob-loc-meta">{r.admin1} · {r.latitude.toFixed(3)}, {r.longitude.toFixed(3)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {form.lat && (
              <div className="ob-loc-selected">📍 {form.location_display} — coordinates saved</div>
            )}
          </div>
        )}

        {/* Camera */}
        {step === "camera" && (
          <div className="ob-step">
            <h2 className="ob-step-title">Camera Setup</h2>
            <p className="ob-step-sub">How is the camera connected to this computer?</p>
            <div className="ob-camera-grid">
              {CAMERA_MODES.map(m => (
                <button
                  key={m.id}
                  className={`ob-camera-card${form.camera_mode === m.id ? " ob-camera-active" : ""}`}
                  onClick={() => set("camera_mode", m.id)}
                >
                  <span className="ob-cam-icon">{m.icon}</span>
                  <span className="ob-cam-label">{m.label}</span>
                  <span className="ob-cam-desc">{m.desc}</span>
                </button>
              ))}
            </div>
            {form.camera_mode === "webcam" && (
              <div className="ob-field">
                <label>Camera Index</label>
                <input className="ob-input ob-input-sm" type="number" min="0" max="9"
                  value={form.camera_source} onChange={e => set("camera_source", e.target.value)} />
                <span className="ob-hint">0 = built-in webcam · 1 = first external USB</span>
              </div>
            )}
            {(form.camera_mode === "rtsp" || form.camera_mode === "http") && (
              <div className="ob-field">
                <label>Stream URL</label>
                <input className="ob-input"
                  placeholder={form.camera_mode === "rtsp"
                    ? "rtsp://admin:pass@192.168.1.100:554/stream"
                    : "http://192.168.1.100:8080/video"}
                  value={form.camera_source} onChange={e => set("camera_source", e.target.value)} />
              </div>
            )}
            {form.camera_mode === "arlo" && (<>
              <div className="ob-field">
                <label>Arlo Email</label>
                <input className="ob-input" type="email" placeholder="you@example.com"
                  value={form.arlo_email} onChange={e => set("arlo_email", e.target.value)} />
              </div>
              <div className="ob-field">
                <label>Arlo Password</label>
                <input className="ob-input" type="password"
                  value={form.arlo_password} onChange={e => set("arlo_password", e.target.value)} />
              </div>
              <div className="ob-field">
                <label>Device Name</label>
                <input className="ob-input" placeholder="e.g. Front Door"
                  value={form.arlo_device} onChange={e => set("arlo_device", e.target.value)} />
              </div>
            </>)}
          </div>
        )}

        {/* Schedule + Review */}
        {step === "schedule" && (
          <div className="ob-step">
            <h2 className="ob-step-title">Preferences</h2>
            <p className="ob-step-sub">Configure AI scheduling and detection sensitivity.</p>
            <div className="ob-two-col">
              <div className="ob-field">
                <label>Day End Time</label>
                <input className="ob-input" type="time"
                  value={form.day_end_time} onChange={e => set("day_end_time", e.target.value)} />
                <span className="ob-hint">Daily AI summary generates at this time</span>
              </div>
              <div className="ob-field">
                <label>Capture Interval (s)</label>
                <input className="ob-input ob-input-sm" type="number" min="1" max="60"
                  value={form.capture_interval} onChange={e => set("capture_interval", e.target.value)} />
                <span className="ob-hint">Seconds between camera frames</span>
              </div>
            </div>
            <div className="ob-field">
              <label>Queue Threshold (people)</label>
              <input className="ob-input ob-input-sm" type="number" min="1" max="20"
                value={form.queue_threshold} onChange={e => set("queue_threshold", e.target.value)} />
              <span className="ob-hint">How many people in a zone triggers a queue alert</span>
            </div>
            <div className="ob-review">
              <div className="ob-review-title">Summary</div>
              <div className="ob-review-grid">
                <span>Store</span>     <span>{form.store_name}</span>
                <span>Location</span>  <span>{form.location_display || `${form.lat}, ${form.lon}`}</span>
                <span>State</span>     <span>{form.state}</span>
                <span>Camera</span>    <span>{CAMERA_MODES.find(m => m.id === form.camera_mode)?.label}</span>
                <span>Day end</span>   <span>{form.day_end_time}</span>
              </div>
            </div>
            {submitError && <div className="ob-error">{submitError}</div>}
          </div>
        )}

        {/* Nav bar (all steps except connect and welcome) */}
        {step !== "connect" && step !== "welcome" && (
          <div className="ob-nav">
            <button className="ob-btn ob-ghost" onClick={goBack}>← Back</button>
            {step !== "schedule" ? (
              <button className="ob-btn ob-primary" disabled={!canAdvance()} onClick={advance}>
                Continue →
              </button>
            ) : (
              <button className="ob-btn ob-primary" disabled={submitting || !canAdvance()} onClick={submit}>
                {submitting ? "Launching…" : "Launch Dashboard →"}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
